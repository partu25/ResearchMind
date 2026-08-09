import re
import os
from dotenv import load_dotenv
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import AIMessage
from tools import web_search, scrape_url

load_dotenv()

# Model setup 
llm = ChatNVIDIA(
    model="nvidia/nemotron-mini-4b-instruct",
    api_key=os.getenv("NVIDIA_API_KEY"),
    temperature=0,
    timeout=120
)

# 1st agent - Search Agent Wrapper
class SearchAgentWrapper:
    def __init__(self, llm):
        self.llm = llm

    def invoke(self, input_dict):
        messages = input_dict.get("messages", [])
        prompt_text = messages[-1][1] if messages else ""
        
        # Extract topic from prompt
        query = prompt_text.replace("Find recent, reliable and detailed information about:", "").strip()
        if not query:
            query = prompt_text
            
        # Execute Tavily search tool directly
        search_output = web_search.invoke(query)
        return {"messages": [AIMessage(content=search_output)]}

# 2nd agent - Reader Agent Wrapper
class ReaderAgentWrapper:
    def __init__(self, llm):
        self.llm = llm

    def invoke(self, input_dict):
        messages = input_dict.get("messages", [])
        text = messages[-1][1] if messages else ""
        
        # Extract first URL from search results
        urls = re.findall(r'https?://[^\s\n"]+', text)
        if urls:
            url = urls[0].rstrip('.,;')
            scraped = scrape_url.invoke(url)
            content = f"Scraped from URL: {url}\n\nContent:\n{scraped}"
        else:
            content = "No URL found to scrape from search results."
            
        return {"messages": [AIMessage(content=content)]}

def build_search_agent():
    return SearchAgentWrapper(llm)

def build_reader_agent():
    return ReaderAgentWrapper(llm)


# Writer chain 
writer_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are an expert research writer. Write clear, structured and insightful reports."),
    ("human", """Write a detailed research report on the topic below.

Topic: {topic}

Research Gathered:
{research}

Structure the report as:
- Introduction
- Key Findings (minimum 3 well-explained points)
- Conclusion
- Sources (list all URLs found in the research)

Be detailed, factual and professional."""),
])

writer_chain = writer_prompt | llm | StrOutputParser()


# Critic chain 
critic_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a sharp and constructive research critic. Be honest and specific."),
    ("human", """Review the research report below and evaluate it strictly.

Report:
{report}

Respond in this exact format:

Score: X/10

Strengths:
- ...
- ...

Areas to Improve:
- ...
- ...

One line verdict:
..."""),
])

critic_chain = critic_prompt | llm | StrOutputParser()
