<p align="center">
  @@@ Logo deleted to maintain anonymity @@@
  
  <div align="center">
    Structure mapping automation based on §sentence embadding<br/>
  </div>
</p>

<p align="center">
  <a href="https://anonymous.4open.science/r/FAME-anonymous-4CE0"><img src="https://img.shields.io/badge/CI-passing-brightgreen?logo=github" alt="ci"/></a>
  <a href="https://hub.docker.com/"><img src="https://img.shields.io/badge/-docker-gray?logo=docker" alt="docker"/></a>
  <a href="https://reactjs.org/"><img src="https://img.shields.io/badge/-react-grey?logo=react" alt="react"/></a>
</p>

# Useage  
**The next part is only partial and does not include Docker for the purpose of maintaining anonymity**

Install dependencies and run on your local PC.  
```bash
git clone **deleted to maintain anonymity**
cd FAME
pip install -r requirements.txt
```  

### Without GUI
Execution is done by configure a yaml file.
Examples for yaml files can be found under: `backend/evalution`, in particular you can use `backend/evalution/playground.yaml`, you can add a new entry in same format.  

```bash
  -m, --model TEXT                The model for sBERT:
                                  https://huggingface.co/sentence-transformers

  -t, --freq-th FLOAT             Threshold for % to take from json
                                  frequencies

  -y, --yaml TEXT                 Path for the yaml for evaluation\

  -c, --comment TEXT              Additional comment for the job

  -s, --specify INTEGER           Specify which entry of the yaml file to
                                  evaluate

  -a, --algo TEXT                 Which algorithm to use

  -g, --num-of-suggestions INTEGER
                                  Number of suggestions for missing entities
```

For running **all** the entries in the yaml file:   
```bash
python backend/evaluation/evaluation.py --yaml playground.yaml
```  
If you want the suggestions to be available, add `--suggestions`.  This is not recommend unless you looking for suggstions.  
**By default, the script is running all the entries in the yaml**. If you want to run specific entry, use `--specify {entry number, start from 1}`. You can specify muliple entries.  
For example, running the first entry only:  
```bash
python backend/evaluation/evaluation.py --yaml playground.yaml --specify 1
```  
Running the first and the third entries:  
```bash
python backend/evaluation/evaluation.py --yaml playground.yaml --specify 1 --specify 3
```  
&nbsp;  

### Using GUI interface
1) Install <a href="https://nodejs.org/en/">Node.js</a>, make sure its in your PATH. Install version 16.13.0.  
2) Now we need to install the react dependencies:  
```bash
cd webapp
npm ci
```  
<!-- 3) In `pakeage.json`, change the proxy from `http://backend:5031` to `http://localhost:5031`, the 'backend' is necessary when running the docker. -->
3) Now back to the root folder, and open the file ./backend/app/app.py, and **uncomment** the if main == ... section below.
4) from the root folder, run:
```bash
python backend/app/app.py
``` 
5) Now we just need to start the frontend:
```bash
cd webapp
npm start
```  
&nbsp;  


**Notice**: for using GPT3 you need to provide an api-key for an environment variable named `OPENAI_API_KEY`, or hand-coded in backend/mapping/gpt3.py