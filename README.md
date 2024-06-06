# M-Agent
This this a chat robot with memory throughout KG!!


# install
Firstly, you need to install the necessary packages

```shell
pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```
Find the version that suits you, and the different versions don't change much  
Then install the other dependencies
```shell
pip install -r requirements.txt
```

To vertify if you are successful, run test.ipynb, which finish the fundamental functions of llama-index

# Config
Firstly, you need to set your .env file 
```
# The information of the QQ-bot, if you don not have please create it at https://q.qq.com/ first.
APPID = 
TOKEN = 
APPSECRET = 


# OPENAI key
API_SECRET_KEY = 
BASE_URL = 

# language
LANGUAGE = Chinese

# Weather key
TOMORROW_API = 
LOCATION = 

# Azure OpenAI Service
AZURE_OPENAI_KEY=
AZURE_OPENAI_ENDPOINT=
```
since the project is not finished yet, the .env file will update while the project is developing


# Our target
* Our short term goal is to learn how to use the llama-index library, and learn how to make the Vector Rag and the Graph Rag, comparing these functions and make a better one to over the efficiency of the previous.
* Our long term goal is to make a chat robot with memory throughout these Rag, this can be the agent that collecting data for you, it can search online and talk to you with its own memory.

# Join us
If you are interested in this project, please contact us.