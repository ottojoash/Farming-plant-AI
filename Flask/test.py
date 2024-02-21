
from dotenv import find_dotenv, load_dotenv
import os
load_dotenv(find_dotenv())
os.getenv("OPENAI_API_KEY")
# import
from langchain.text_splitter import CharacterTextSplitter
from langchain_community.document_loaders import TextLoader
from langchain_community.embeddings.sentence_transformer import (
    SentenceTransformerEmbeddings,
)
from langchain_community.vectorstores import Chroma
from langchain_community.document_loaders import DirectoryLoader


# load the document and split it into chunks
# loader = TextLoader("../../modules/state_of_the_union.txt")
loader = DirectoryLoader('./chromadocs', glob="**/*.md", show_progress=True,use_multithreading=True)


documents = loader.load()

# split it into chunks
text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=0)
docs = text_splitter.split_documents(documents)

# create the open-source embedding function
embedding_function = SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")

# load it into Chroma
# db = Chroma.from_documents(docs, embedding_function)
db = Chroma(persist_directory="./chroma_db", embedding_function=embedding_function)

# retriever = db.as_retriever()
retriever = db.as_retriever(search_type="mmr")



# query it
query = "what is a plant disease and give me examples"
# docs = db.similarity_search(query)
docs = retriever.get_relevant_documents(query)
# print results
print(docs[0].page_content)


#*******************************

# from langchain.agents import AgentType, Tool, initialize_agent
# from langchain_community.utilities import GoogleSerperAPIWrapper
# from langchain_community.llms import OpenAI  # Update the import statement

# llm = OpenAI(temperature=0)
# search = GoogleSerperAPIWrapper()
# tools = [
#     Tool(
#         name="Intermediate Answer",
#         func=search.run,
#         description="useful for when you need to ask with search",
#     )
# ]

# self_ask_with_search = initialize_agent(
#     tools, llm, agent=AgentType.SELF_ASK_WITH_SEARCH, verbose=True
# )
# self_ask_with_search.run(
#     "What is the hometown of the reigning men's U.S. Open champion?"
# )