import os

from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

# llm = ChatGoogleGenerativeAI(
#     model="gemini-2.0-flash",
#     temperature=0,
#     google_api_key=os.getenv("GOOGLE_API_KEY")
# )

import os
from langchain_groq import ChatGroq

# llm = ChatGroq(
#     model="llama-3.3-70b-versatile",
#     temperature=0,
#     api_key=os.getenv("GROQ_API_KEY"),
# )

from langchain_openai import AzureChatOpenAI

llm = AzureChatOpenAI(
    model="gpt-4o-mini",
    api_key="HKFYqFP2TNm86rpPno2N60UbQwHXhMCrS7iKjdpzLfIepWHTxTaxJQQJ99BCACYeBjFXJ3w3AAABACOG8Ajn",
    azure_endpoint=f"https://apusegtodvoai01.openai.azure.com",
    api_version="2025-01-01-preview",
    # temperature=0.001,
    temperature=0
 
)