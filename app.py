from typing import Dict, List
import os
from flask import Flask, render_template, request, jsonify, Response, stream_with_context, session
from dotenv import load_dotenv
from openai import OpenAI
from tenacity import retry, wait_random_exponential, stop_after_attempt

# Load environment variables once
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

GPT_MODEL = 'gpt-4o-mini'
STREAM = True

# Initialize the OpenAI client once
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Retry decorator for API calls to handle temporary failures
@retry(wait=wait_random_exponential(multiplier=1, max=40), stop=stop_after_attempt(3))
def chat_completion_request(messages: List[Dict], tools: List[Dict] = None, tool_choice: str = None, model: str = GPT_MODEL, stream: bool = STREAM):
    try:
        kwargs = {'model': model, 'messages': messages, 'stream': stream}
        if tools:
            kwargs['tools'] = tools
            kwargs['tool_choice'] = tool_choice
        response = client.chat.completions.create(**kwargs)
        if stream:
            return response  # Stream responses return an iterator
        return response
    except Exception as e:
        print('Unable to generate ChatCompletion response')
        print(f'Exception: {e}')
        return e

class Agent:
    def __init__(self, model: str = GPT_MODEL, system_prompt: Dict = None, tools: List[Dict] = None):
        self.model = model
        self.memory = []
        self.tools = tools if tools else []
        if system_prompt:
            self.append_to_memory(system_prompt)

    def append_to_memory(self, memory_content: Dict) -> None:
        """Appends a dict to memory.

        Args:
            memory_content (Dict): {'role': {role}, 'content', {content}}
        """
        if 'role' not in memory_content or 'content' not in memory_content:
            raise ValueError("Memory content must have 'role' and 'content' keys")
        self.memory.append(memory_content)

    def invoke(self, message: str):
        # Add user message to memory and make API call
        self.append_to_memory({'role': 'user', 'content': message})
        return chat_completion_request(messages=self.memory, tools=self.tools, model=self.model, stream=STREAM)

    def _handle_stream_response(self, response) -> str:
        # Process streaming response from API
        final_response = ""
        for chunk in response:
            if hasattr(chunk.choices[0].delta, 'content'):
                chunk_content = chunk.choices[0].delta.content
                if chunk_content is not None:
                    final_response += chunk_content
                    yield f"data: {chunk_content}\n\n" # Format for server-sent events
            # TODO: Implement tool calls handling for streaming responses
            elif hasattr(chunk.choices[0].delta, 'tool_calls'):
                print("Tool call detected in stream response:", chunk.choices[0].delta.tool_calls)
        # Add complete response to agent's memory
        self.append_to_memory({'role': 'assistant', 'content': final_response})
        yield "data: [DONE]\n\n" # Signal end of stream

    def _handle_non_stream_response(self, response) -> str:
        # Process non-streaming response from API
        if response.choices[0].finish_reason == 'stop':
            chat_response_message = response.choices[0].message.content
            self.append_to_memory({'role': 'assistant', 'content': chat_response_message})
            return chat_response_message
        elif response.choices[0].finish_reason == 'tool_calls':
            # TODO: Implement tool calls handling for non-streaming responses
            print("Tool call detected in non-stream response:", response.choices[0].message.tool_calls)
            return "Tool call detected. This functionality is not yet implemented."
        
    def to_dict(self):
        # Serialize agent state for session storage
        return {
            'model': self.model,
            'memory': self.memory,
            'tools': self.tools            
        }
    
    @classmethod
    def from_dict(cls, data):
        # Deserialize agent state from session storage
        agent = cls(model=data['model'])
        agent.memory = data['memory']
        agent.tools = data['tools']
        return agent        

def get_agent():
    # Retrieve or create agent from session data
    if 'agent_data' not in session:
        agent = Agent(system_prompt={"role": "system", "content": "You are a helpful assistant for crypto trading strategies."})
        session['agent_data'] = agent.to_dict()
    else:
        agent = Agent.from_dict(session['agent_data'])
    return agent


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/backtesting')
def backtesting():
    return render_template('backtesting.html', title='Backtesting')

@app.route('/automation')
def automation():
    return render_template('automation.html', title='Automation')

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_message = data.get('message')
    
    agent = get_agent()
    response = agent.invoke(user_message)
    
    # Persist updated agent state in session
    session['agent_data'] = agent.to_dict()
    
    if STREAM:
        # Return streaming response
        return Response(stream_with_context(agent._handle_stream_response(response)), content_type='text/event-stream')
    else:
        # Return non-streaming response
        return jsonify({"response": agent._handle_non_stream_response(response)})
    
@app.route('/clear_memory', methods=['POST'])
def clear_memory():
    # Remove agent data from session, effectively clearing its memory
    if 'agent_data' in session:
        del session['agent_data']
    return jsonify({"message": "Memory cleared successfully"})

@app.route('/set_backtest_params', methods=['POST'])
def set_backtest_params():
    data = request.json
    instrument = data.get('instrument')
    timeframe = data.get('timeframe')
    
    # Store selections in the session
    session['backtest_instrument'] = instrument
    session['backtest_timeframe'] = timeframe
    
    return jsonify({"status": "success", "message": "Backtest parameters set successfully"})

if __name__ == '__main__':
    app.run(debug=True)