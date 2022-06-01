import os
import json
import copy
from pathlib import Path
from typing import List, Tuple, Set, Dict

from click import secho

from . import openIE
from utils import utils
from . import google_autosuggest
from .quasimodo import Quasimodo
from .mapping import Cache, Solution, Pair, SingleMatch, Unmutables
from .mapping import update_already_mapping, update_paris_map, get_all_possible_pairs_map, get_best_pair_mapping

root = Path(__file__).resolve().parent.parent.parent
IGNORE_SUGGESTION = ["the", "they", "us", "we", "you", 'i']

class Suggestions(object):
    def __init__(self, entity: str, prop: str, api: dict, quasimodo: Quasimodo):
        self.entity = entity
        self.prop = prop
        self.api = api
        self.quasimodo = quasimodo
        if api.get("google", False):
            self.google_suggestinos = utils.read_json(root / 'backend' / 'database' / 'google_suggestinos.json')
        if api.get("openie", False):
            self.openie_suggestinos = utils.read_json(root / 'backend' / 'database' / 'openie_suggestinos.json')
        if api.get("quasimodo", False):
            self.quasimodo_suggestinos = utils.read_json(root / 'backend' / 'database' / 'quasimodo_suggestinos.json')

    def get_suggestions(self):
        if self.api.get("quasimodo", False):
            if f"{self.entity}#{self.prop}" in self.quasimodo_suggestinos:
                quasimodo_suggestinos = self.quasimodo_suggestinos[f"{self.entity}#{self.prop}"]
            else:
                quasimodo_suggestinos = self.quasimodo.get_entity_suggestions(self.entity, self.prop, n_largest=5, plural_and_singular=True)
                self.quasimodo_suggestinos[f"{self.entity}#{self.prop}"] = quasimodo_suggestinos  
                with open(root / 'backend' / 'database' / 'quasimodo_suggestinos.json', 'w') as f2:
                    json.dump(self.quasimodo_suggestinos, f2, indent='\t')
        else:
            quasimodo_suggestinos = []

        if 'SKIP_GOOGLE' not in os.environ and self.api.get("google", False):
            if f"{self.entity}#{self.prop}" in self.google_suggestinos:
                google_suggestinos = self.google_suggestinos[f"{self.entity}#{self.prop}"]
            else:
                google_suggestinos = google_autosuggest.get_entity_suggestions(self.entity, self.prop)
                self.google_suggestinos[f"{self.entity}#{self.prop}"] = google_suggestinos  
                with open(root / 'backend' / 'database' / 'google_suggestinos.json', 'w') as f1:
                    json.dump(self.google_suggestinos, f1, indent='\t')
        else:
            google_suggestinos = []

        if self.api.get("openie", False):
            if f"{self.entity}#{self.prop}" in self.openie_suggestinos:
                openie_suggestinos = self.openie_suggestinos[f"{self.entity}#{self.prop}"]
            else:
                openie_suggestinos = openIE.get_entity_suggestions_wrapper(self.entity, self.prop, n_largest=5)
                self.openie_suggestinos[f"{self.entity}#{self.prop}"] = openie_suggestinos  
                with open(root / 'backend' / 'database' / 'openie_suggestinos.json', 'w') as f3:
                    json.dump(self.openie_suggestinos, f3, indent='\t')
        else:
            openie_suggestinos = []

        suggestions = google_suggestinos + quasimodo_suggestinos + openie_suggestinos
        return [suggestion for suggestion in suggestions if suggestion not in IGNORE_SUGGESTION]


def get_suggestions_for_missing_entities(base_not_mapped_entity: str, 
                                         base_already_mapping: List[str], 
                                         target_already_mapping: List[str],
                                         unmutables: Dict[str, Unmutables],
                                         args: dict
                                         ) -> List[str]:
    suggests_list = {}
    # we need all the relations between the entity (the one that not mapped) to the entities that already mapped (again - in the same domain)
    for idx, base_entity in enumerate(base_already_mapping):
        # we going to use the map that we already know (base_entity -> match_target_entity)
        match_target_entity = target_already_mapping[idx]
        if args["verbose"]: 
            secho(f"(^{base_not_mapped_entity}, {base_entity})", fg="blue", bold=True)
            secho(f"  {match_target_entity}", fg="red", bold=True)

        relations1 = unmutables["data_collector"].get_entities_relations(base_entity, base_not_mapped_entity)
        relations2 = unmutables["data_collector"].get_entities_relations(base_not_mapped_entity, base_entity)        

        actual_suggestions = []
        # we going to run over the relations we found, and extract suggestions with them.
        for relation in set(relations1 + relations2):
            suggestions_model = Suggestions(match_target_entity, relation, api=args, quasimodo=unmutables["data_collector"].quasimodo)
            suggestions = suggestions_model.get_suggestions()
            # We take only 1 or 2 tokens (since it should be nouns).
            suggestions = [p for p in suggestions if len(p.split()) <= 2]
            if suggestions:
                # suggestions are found.
                actual_suggestions.extend(suggestions)
                if args["verbose"]:
                    secho(f"    {relation}: ", fg="green", bold=True, nl=False)
                    secho(f"{list(set(suggestions))}", fg="cyan")
        
        if args["verbose"]: 
            if not relations1 + relations2:
                secho(f"    No match found!", fg="green")
            print()
        
        # define how tight are the clusters. We want them to be tight enougth for not loosing suggestions,
        # but not too much, because the idea is to clustering to reduce computations.
        cluster_distance_threshold = 0.6
        clusters = {v[0]: v for _, v in unmutables["model"].clustering((actual_suggestions), cluster_distance_threshold).items()}

        # because we taking suggestions from few sources (quasimodo, openIE, google) we expect to get duplicates
        # suggestions (with the exact name or near), in other words - we expect that the clusters length will be 
        # bigger then 1. If not, it may point to a noise. 0 do nothing.
        cluster_length_threshold = 0
        clusters_filtered = {k: sorted(list(set(v))) for k, v in clusters.items() if len(v) > cluster_length_threshold} # sorting for consistency
        suggests_list[match_target_entity] = clusters_filtered
        
    return suggests_list


def get_new_domains(first_domain: str, solution: Solution, entity_not_mapped_yet: str, clusters_representors: List[str]) -> dict:
    if first_domain == "actual_base":
        new_base = solution.get_actual("actual_base") + [entity_not_mapped_yet]
        new_target = solution.get_actual("actual_target") + clusters_representors
        index_domain = 1
        
    else: # first_domain == "actual_target"
        new_base = solution.get_actual("actual_base") + clusters_representors
        new_target = solution.get_actual("actual_target") + [entity_not_mapped_yet]
        index_domain = 0
    
    return {
        "new_base": new_base,
        "new_target": new_target,
        "index_domain": index_domain,
    }


def mapping_suggestions_create_new_solution(
    available_pairs: List[List[SingleMatch]],
    current_solution: Solution,
    solutions: List[Solution],
    top_suggestions: List[str],
    domain: str,
    unmutables: Dict[str, Unmutables],
    cache: Dict[str, Cache],
    args: dict):
    """this function is use for mapping in suggestions mode. this is only one iteration"""
    
    # we will get the top-num-of-suggestions with the best score.
    best_results_for_current_iteration = get_best_pair_mapping(unmutables, available_pairs, cache, args["N"])
    for result in best_results_for_current_iteration:
        # if the best score is > 0, we will update the base and target lists of the already mapping entities.
        # otherwise, if the best score is 0, we have no more mappings to do.
        if result["best_score"] > 0:
            # we will add the new mapping to the already mapping lists. 
            base_already_mapping_new = copy.deepcopy(current_solution.actual_base)
            target_already_mapping_new = copy.deepcopy(current_solution.actual_target)
            actual_mapping_indecies_new = copy.deepcopy(current_solution.actual_indecies)
            b1, b2 = result["best_mapping"][0][0], result["best_mapping"][0][1]
            t1, t2 = result["best_mapping"][1][0], result["best_mapping"][1][1]
            
            score = 0
            if b1 not in base_already_mapping_new and t1 not in target_already_mapping_new:
                score += result["best_score"]
                # score += get_score(base_already_mapping_new, target_already_mapping_new, b1, t1, cache)
                update_already_mapping(b1, t1, base_already_mapping_new, target_already_mapping_new, actual_mapping_indecies_new)
            
            if b2 not in base_already_mapping_new and t2 not in target_already_mapping_new:
                score += result["best_score"]
                # score += get_score(base_already_mapping_new, target_already_mapping_new, b2, t2, cache)
                update_already_mapping(b2, t2, base_already_mapping_new, target_already_mapping_new, actual_mapping_indecies_new)
            
            mapping_repr = [f"{b} --> {t}" for b, t in zip(base_already_mapping_new, target_already_mapping_new)]
            mapping_repr_as_tuple = tuple(sorted(mapping_repr))
            if mapping_repr_as_tuple in cache["mappings"]:
                continue
            cache["mappings"].add(mapping_repr_as_tuple)
            
            # sometimes it found the same entity
            if target_already_mapping_new[-1] == base_already_mapping_new[-1]:
                continue
            
            # we need to add the mapping that we just found to the relations that already exist for that solution.
            relations = copy.deepcopy(current_solution.relations)
            relations.append(result["best_mapping"])
            scores_copy = copy.deepcopy(current_solution.scores)
            scores_copy.append(round(result["best_score"], 3))
            coverage = copy.deepcopy(current_solution.coverage)
            coverage.append(result["coverage"])
            
            relations_as_tuple = tuple([tuple(relation) for relation in sorted(relations)])
            if relations_as_tuple in cache["relations"]:
                continue
            cache["relations"].add(relations_as_tuple)
                
            # updating the top suggestions for the GUI
            if domain == "actual_base":
                top_suggestions.append(target_already_mapping_new[-1])
            elif domain == "actual_target":
                top_suggestions.append(base_already_mapping_new[-1])
                
            solutions.append(Solution(
                mapping=[f"{b} --> {t}" for b, t in zip(base_already_mapping_new, target_already_mapping_new)],
                relations=relations,
                scores=scores_copy,
                score=round(current_solution.score + score, 3),
                actual_base=base_already_mapping_new,
                actual_target=target_already_mapping_new,
                actual_indecies=actual_mapping_indecies_new,
                length=len(base_already_mapping_new),
                coverage=coverage,
            ))


def mapping_suggestions_helper(
    suggestions: List[str], 
    domain: str, 
    entity_not_mapped_yet: str, 
    solution: Solution,
    entity_from_second_domain: str,
    solutions: List[Solution],
    unmutables: Dict[str, Unmutables],
    cache: Dict[str, Cache],
    args: dict,
    top_suggestions: List[str]
    ):
    if not suggestions:
        return  # no suggestion found :(
    
    # get new base and target. For example, if we had B=[earth, gravity], T=[electron, electricity] and 'sun'
    # is the entity that not mapped yet, we will now should have: B=[earth, gravity, sun], T=[electron, electricity, t1, t2, t3, ...]
    res = get_new_domains(domain, solution, entity_not_mapped_yet, suggestions)
    new_base = res["new_base"]
    new_target = res["new_target"]
    index_domain = res["index_domain"]

    all_pairs = get_all_possible_pairs_map(new_base, new_target)
    available_pairs = update_paris_map(all_pairs, solution.get_actual("actual_base"), solution.get_actual("actual_target"), solution.actual_indecies)
    
    # in the current iteration, if the relations (clusters now) came from earth:sun, and we know that
    # earth->electron, we allow only pairs that contains electron:t_i. Where t_i are the new suggsetions.
    pair_allows: Set[Tuple[str, str]] = set([(entity_from_second_domain, v) for v in suggestions])
    available_pairs = [pair for pair in available_pairs if pair[0][index_domain] in pair_allows]
    if not available_pairs:
        return
    
    mapping_suggestions_create_new_solution(
        available_pairs=available_pairs,
        current_solution=copy.deepcopy(solution),
        solutions=solutions,
        top_suggestions=top_suggestions,
        domain=domain,
        unmutables=unmutables,
        cache=cache,
        args=args,
    )


def mapping_suggestions(
    domain: List[str],
    first_domain: str, 
    second_domain: str, 
    solution: Solution,
    solutions: List[Solution],
    unmutables: Dict[str, Unmutables],
    cache: Dict[str, Cache],
    args: dict):
    
    first_domain_not_mapped_entities = [entity for entity in domain if entity not in solution.get_actual(first_domain)]
    if not first_domain_not_mapped_entities:
        return
    # as we sayd before, we supporting only one missing entity for now.
    assert(len(first_domain_not_mapped_entities) == 1)
    entity_not_mapped_yet = first_domain_not_mapped_entities[0]

    # we will go over and entities from the first domain and extract the relations with 'entity_not_mapped_yet'
    # then, we will store in a dict the key which is the corresponding entity from the second domain, and in the value the relations.
    # for example, if the first domain is [earth, gravity], and the entity not mapped yet is 'sun', we will extract all the relations
    # between earth:sun and gravity:sun. So if we already know that earth->electron and gravity->electricity, we will store in the
    # dict {'electron': earth:sun, 'electricity': gravity:sun}. remember that the syntax e1:e2 is list of relations (str).
    entities_suggestions: Dict[str, List[str]] = get_suggestions_for_missing_entities(  entity_not_mapped_yet, 
                                                                                        solution.get_actual(first_domain), 
                                                                                        solution.get_actual(second_domain), 
                                                                                        unmutables=unmutables,
                                                                                        args=args)
    
    total_suggestions = []
    # we want to reduce unnecessary computations. So we instead of running over all the suggestions.
    # in 'get_suggestions_for_missing_entities' we split the suggestions into tight clusters. 
    # for example, we may have a cluster that look like: [franklin, ben franklin, benjamin franklin, benjamin]. 
    # So we take a representor (the first one), and put it as key of the cluster. And of course the value is all the cluster.
    for key, value in entities_suggestions.items():
        # the first step is to go over all the representors of the clusters (instead of all the suggestions).
        clusters_representors = list(value.keys())
        top_suggestions = []
        mapping_suggestions_helper( clusters_representors, 
                                    first_domain, 
                                    entity_not_mapped_yet, 
                                    solution, 
                                    key,
                                    solutions,
                                    unmutables,
                                    cache,
                                    args,
                                    top_suggestions)
        
        if top_suggestions: # TODO: check how is possible that this can be empty
            # this is the number of cluster we want to "go inside" to check all the relations.
            # ideally (from the computation view), we want it to be 1. But someitmes we may loose 
            # good suggestions just because the cluster represntor.
            number_of_top_clusters_to_check = 3

            for cluster_representor in top_suggestions[:number_of_top_clusters_to_check]:
                best_cluster_suggestions = value[cluster_representor]
                best_cluster_suggestions.remove(cluster_representor)
                mapping_suggestions_helper( best_cluster_suggestions, 
                                            first_domain, 
                                            entity_not_mapped_yet, 
                                            solution, 
                                            key,
                                            solutions,
                                            unmutables,
                                            cache,
                                            args,
                                            top_suggestions)
        
        # using just for knowing how many solutions added in that call.
        total_suggestions.extend(top_suggestions)
    
    # lets make it more clear with the suggestions.
    # for the current solution, we will extract all suggestions.
    cut_off = len(solutions) - len(total_suggestions)
    solutions_of_current_call = solutions[cut_off:]
    solutions_of_current_call_with_suggestion = [(solution_, suggestion_) for solution_, suggestion_ in zip(solutions_of_current_call, total_suggestions)]
    solutions_of_current_call_with_suggestion = sorted(solutions_of_current_call_with_suggestion, key=lambda x: (x[0].length, x[0].score), reverse=True)
    top_suggestions_ordered = [suggestion for _, suggestion in solutions_of_current_call_with_suggestion]

    for i in range(cut_off, len(solutions)):
        solutions[i].top_suggestions = top_suggestions_ordered[:args["num_of_suggestions"]]


def mapping_suggestions_wrapper(
    base: List[str], 
    target: List[str],
    solutions: List[Solution],
    args: dict,
    unmutables: Dict[str, Unmutables],
    cache: Dict[str, Cache]
    ) -> List[Solution]:

    # array of addition solutions for the suggestions if some entities have missing mappings.
    suggestions_solutions = []
    if args["num_of_suggestions"] > 0:
        # we want to work only on the best solutions.
        solutions = sorted(solutions, key=lambda x: (x.length, x.score), reverse=True)
        # all the following will happen only if there are missing mapping for some entity.
        if solutions and solutions[0].length < max(len(base), len(target)):
            # this parameter allows us to look not only on the best result.
            # this relevant when the suggestion is for a strong one.
            # for example, if B=[earth, gravity], T=[nucleus, electron, electricity].
            # The best solution may hold earth:gravity~nucleus:electricity, but this
            # is only because 'sun' is not in the picture, yet. 
            number_of_solutions_for_suggestions = 3
            
            # the idea is to iterate over the founded solutions, and check if there are entities that not mapped.
            for solution in solutions[:number_of_solutions_for_suggestions]:
                if solution.length < max(len(base), len(target)) - 1:
                    # this logic is checked only if ONE entity have missing mapping (from base or target)
                    # the complication for two or more missing entities is too complicated. Better to asked
                    # from the user to be more specific.
                    continue
                
                mapping_suggestions(domain=base, 
                                    first_domain="actual_base", 
                                    second_domain="actual_target", 
                                    solution=solution,
                                    solutions=suggestions_solutions,
                                    unmutables=unmutables,
                                    cache=cache, 
                                    args=args)
                
                mapping_suggestions(domain=target, 
                                    first_domain="actual_target", 
                                    second_domain="actual_base", 
                                    solution=solution,
                                    solutions=suggestions_solutions,
                                    unmutables=unmutables,
                                    cache=cache, 
                                    args=args)                
    return suggestions_solutions
        

if __name__ == '__main__':
    pass
    # res = get_best_matches_for_entity("newton", ["faraday", "sky", "window", "paper", "photo", "apple", "tomato", "wall", "home", "horse"])
    # print(res)