# app.py
from langchain_community.llms import OpenAI  # Update the import statement

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from langchain_community.chat_models import ChatOpenAI
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain.prompts import PromptTemplate
from dotenv import find_dotenv, load_dotenv
import os
from flask import Flask, render_template, jsonify, request
from model import predict_image
import utils
# from langchain_integration import LangChainHelper
from markupsafe import Markup

load_dotenv(find_dotenv())

app = Flask(__name__)

# langchain_helper = LangChainHelper()
def predictUsinLangchain (input):
    
    
    template = """You are a plant disease research expert , 
    who helps junior researchers with their tasks regarding the diffrent work

    {chat_history}
    Human: {human_input}
    Chatbot:"""

    prompt = PromptTemplate(
    input_variables=["chat_history", "human_input"], template=template
    )
    memory = ConversationBufferMemory(memory_key="chat_history")
    llm = OpenAI()
    llm_chain = LLMChain(
    llm=llm,
    prompt=prompt,
    verbose=True,
    memory=memory,
    )
    results = llm_chain.predict(human_input=input)
    print(results)
    return (results)

    
@app.route('/', methods=['GET'])
def home():
    return render_template('index.html')

@app.route('/predict',methods=['POST'])
def predict():
    if request.method == 'POST':
        file = request.files.get('file')
        
        print(file)
        if not file:
            return render_template('index.html', status=400, res="No file provided")

        try:
            img = file.read()
            prediction = predict_image(img)
           
            
            if prediction in utils.disease_dic:  # Example threshold /*and accuracy*/
                res = Markup(utils.disease_dic[prediction])
            else:
             
                langchain_prediction =predictUsinLangchain(res)
                print(langchain_prediction)
                res = Markup(langchain_prediction) if langchain_prediction else Markup("Unable to identify the disease.")

            return render_template('display.html', status=200, result=res)
        except Exception as e:
            print(f"An error occurred during prediction: {e}")
            return render_template('index.html', status=500, res="Internal Server Error")
    else:
        return render_template('index.html')

if __name__ == "__main__":
    app.run(debug=True)
