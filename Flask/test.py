
from dotenv import find_dotenv, load_dotenv
import os

from langchain_openai import OpenAIEmbeddings
load_dotenv(find_dotenv())
os.getenv("OPENAI_API_KEY")



# # import
# from langchain.text_splitter import CharacterTextSplitter
# from langchain_community.document_loaders import TextLoader
# from langchain_community.embeddings.sentence_transformer import (
#     SentenceTransformerEmbeddings,
# )
# from langchain_community.vectorstores import Chroma


# # load the document and split it into chunks
# loader = TextLoader("C:\\Users\\JOASH\\Downloads\\Compressed\\Farming-plant-AI-master\\Flask\\chromadocs\\PPA-46.txt")
# documents = loader.load()

# # split it into chunks
# text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=0)
# docs = text_splitter.split_documents(documents)

# # create the open-source embedding function
embedding_function = OpenAIEmbeddings(model="text-embedding-3-large")

# # embedding_function = SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")
# db= Chroma.from_documents(docs, embedding_function, persist_directory="./chroma_db")

# # query it
# query = "what is a plant"
# docs = db.similarity_search(query)

# # print results
# print(docs[0].page_content)

from langchain_core.messages import AIMessage
from langchain_core.messages import HumanMessage

from langchain.vectorstores import Chroma
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.chains.combine_documents import create_stuff_documents_chain

llm = ChatOpenAI(model="gpt-3.5-turbo-1106", temperature=0.2)

embedding = OpenAIEmbeddings()
vectordb = Chroma(persist_directory="./chroma_db", embedding_function=embedding)
print(vectordb._collection.count())

db = Chroma(persist_directory="./chroma_db", embedding_function=embedding_function)

# retriever = db.as_retriever(search_type="mmr")
query="what is a plant disease"
retriever = db.as_retriever(k=1)

docs = retriever.invoke(query)



chat = ChatOpenAI(model="gpt-3.5-turbo-1106")

question_answering_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Answer the user's questions based on the below context:\n\n{context}",
        ),
        MessagesPlaceholder(variable_name="messages"),
    ]
)

document_chain = create_stuff_documents_chain(chat, question_answering_prompt)

# print(document_chain)
from langchain.memory import ChatMessageHistory

demo_ephemeral_chat_history = ChatMessageHistory()

demo_ephemeral_chat_history.add_user_message(query)

res = document_chain.invoke(
    {
        "messages": demo_ephemeral_chat_history.messages,
        "context": docs,
    }
)
print(res)