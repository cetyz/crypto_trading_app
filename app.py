from typing import Dict, List
import os
import json
from flask import Flask, render_template, request, jsonify, Response, stream_with_context, session
from dotenv import load_dotenv
from openai import OpenAI
from tenacity import retry, wait_random_exponential, stop_after_attempt

# Load environment variables once
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

STRATEGIES_DIR = 'user_strategies'
os.makedirs(STRATEGIES_DIR, exist_ok=True)

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

def summarize_strategy(chat_history):
    response = client.chat.completions.create(
        model=GPT_MODEL,
        messages=[
            {"role": "system", "content": "You are a Strategy Summarizer Agent. Your task is to analyze the chat history and extract a clear, concise summary of the trading strategy discussed. Your summary should include the following: 1. Entry Condition 2. Exit Condition 3. Position Sizing 4. Stop Loss Condition 5. Take Profit Condition \n\n"},
            {"role": "user", "content": f"Summarize the trading strategy from this chat history:\n\n{chat_history}"}
        ]
    )
    return response.choices[0].message.content

def generate_strategy_json(strategy_summary):
    response = client.chat.completions.create(
        model=GPT_MODEL,
        messages=[
            {"role": "system", "content": """You are an expert in creating trading strategies. Your task is to convert the provided strategy summary into a structured JSON representation.
             Example strategy summary:
             Strategy Name: Simple Moving Average Crossover Strategy
             Strategy Summary: Using a fast period of 10, and slow period of 50, entry condition is when the fast SMA crosses over the slow SMA. Exit condition is when fast SMA crosses below the slow SMA. Use a fixed position size of 100. Stop loss will be 2 percent below entry price. Take profit will be 5 percent above entry price.
             
             Example output (not perfect formatting, just to convey the example):
             strategy_name: Simple Moving Average Crossover Strategy

             entry_condition: {
             indicator: SMA,
             parameter_1: {
             name: fast_period,
             value: 10
             },
             parameter_2: {
             name: slow_period,
             value: 50
             },
             parameter_3: {
             name: N/A,
             value: 0
             },
             condition: fast SMA crosses above slow SMA
             }
             
             exit_condition: {
             indicator: SMA,
             parameter_1: {
             name: fast_period,
             value: 10
             },
             parameter_2: {
             name: slow_period,
             value: 50
             },
             parameter_3: {
             name: N/A,
             value: 0
             },
             condition: fast SMA crosses below slow SMA
             }

             position_size: {
             type: fixed,
             value: 100
             }

             stop_loss: {
             parameter_1: {
             name: percentage of entry price,
             value: 2
             },
             parameter_2: {
             name: N/A
             value: 0
             },
             parameter_3: {
             name: N/A,
             value: 0
             },
             condition: price falls below entry price
             }

             take_profit: {
             parameter_1: {
             name: percentage of entry price,
             value: 5
             },
             parameter_2: {
             name: N/A
             value: 0
             },
             parameter_3: {
             name: N/A,
             value: 0
             },
             condition: price goes above entry price             
             }

             """},
            {"role": "user", "content": f"Create a JSON representation of this strategy:\n\n{strategy_summary}"}
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "strategy_to_json",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "strategy_name": {
                            "type": "string"
                        },
                        "entry_condition": {
                            "type": "object",
                            "properties": {
                                "indicator": {"type": "string"},
                                "condition": {"type": "string"},
                                "parameter_1": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "value": {"type": "integer"},
                                    },
                                    "required": ["name", "value"],
                                    "additionalProperties": False
                                },
                                "parameter_2": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "value": {"type": "integer"},
                                    },
                                    "required": ["name", "value"],
                                    "additionalProperties": False
                                },
                                "parameter_3": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "value": {"type": "integer"},
                                    },
                                    "required": ["name", "value"],
                                    "additionalProperties": False
                                },                                
                            },
                            "required": ["indicator", "condition", "parameter_1", "parameter_2", "parameter_3"],
                            "additionalProperties": False
                        },
                        "exit_condition": {
                            "type": "object",
                            "properties": {
                                "indicator": {"type": "string"},
                                "condition": {"type": "string"},
                                "parameter_1": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "value": {"type": "integer"},
                                    },
                                    "required": ["name", "value"],
                                    "additionalProperties": False
                                },
                                "parameter_2": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "value": {"type": "integer"},
                                    },
                                    "required": ["name", "value"],
                                    "additionalProperties": False
                                },
                                "parameter_3": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "value": {"type": "integer"},
                                    },
                                    "required": ["name", "value"],
                                    "additionalProperties": False
                                },   
                            },
                            "required": ["indicator", "condition", "parameter_1", "parameter_2", "parameter_3"],
                            "additionalProperties": False
                        },
                        "position_size": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string"},
                                "value": {"type": "integer"},
                            },
                            "required": ["type", "value"],
                            "additionalProperties": False
                        },
                        "stop_loss": {
                            "type": "object",
                            "properties": {
                                "condition": {"type": "string"},
                                "parameter_1": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "value": {"type": "integer"},
                                    },
                                    "required": ["name", "value"],
                                    "additionalProperties": False
                                },
                                "parameter_2": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "value": {"type": "integer"},
                                    },
                                    "required": ["name", "value"],
                                    "additionalProperties": False
                                },
                                "parameter_3": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "value": {"type": "integer"},
                                    },
                                    "required": ["name", "value"],
                                    "additionalProperties": False
                                },   
                            },
                            "required": ["condition", "parameter_1", "parameter_2", "parameter_3"],
                            "additionalProperties": False
                        },
                        "take_profit": {
                            "type": "object",
                            "properties": {
                                "condition": {"type": "string"},
                                "parameter_1": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "value": {"type": "integer"},
                                    },
                                    "required": ["name", "value"],
                                    "additionalProperties": False
                                },
                                "parameter_2": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "value": {"type": "integer"},
                                    },
                                    "required": ["name", "value"],
                                    "additionalProperties": False
                                },
                                "parameter_3": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "value": {"type": "integer"},
                                    },
                                    "required": ["name", "value"],
                                    "additionalProperties": False
                                },   
                            },
                            "required": ["condition", "parameter_1", "parameter_2", "parameter_3"],
                            "additionalProperties": False
                        },
                    },
                    "required": ["strategy_name", "entry_condition", "exit_condition", "position_size", "stop_loss", "take_profit"],
                    "additionalProperties": False
                }
            }
        }
    )
    return response.choices[0].message.content

def get_user_strategies_file():
    user_id = session.get('user_id', 'default_user')  # You should implement proper user authentication
    return os.path.join(STRATEGIES_DIR, f"{user_id}_strategies.json")

def load_user_strategies():
    file_path = get_user_strategies_file()
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            return json.load(f)
    return []

def save_user_strategies(strategies):
    file_path = get_user_strategies_file()
    with open(file_path, 'w') as f:
        json.dump(strategies, f, indent=2)


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

@app.route('/generate_strategy', methods=['POST'])
def generate_strategy():
    chat_history = request.json.get('chat_history')
    
    # Step 3: Summarize the strategy
    strategy_summary = summarize_strategy(chat_history)
    
    # Step 4: Generate JSON from the summary
    strategy_json = generate_strategy_json(strategy_summary)
    
    # Store the summary for front-end use
    session['current_strategy_summary'] = strategy_summary
    
    return jsonify({
        "strategy_summary": strategy_summary,
        "strategy_json": strategy_json
    })

@app.route('/get_current_strategy', methods=['GET'])
def get_current_strategy():
    return jsonify({
        "strategy_summary": session.get('current_strategy_summary', "No strategy currently selected.")
    })

@app.route('/save_strategy', methods=['POST'])
def save_strategy():
    new_strategy = request.json
    strategies = load_user_strategies()
    strategies.append(new_strategy)
    save_user_strategies(strategies)
    return jsonify({"message": "Strategy saved successfully", "strategies": strategies})

@app.route('/get_strategies', methods=['GET'])
def get_strategies():
    strategies = load_user_strategies()
    return jsonify(strategies)

@app.route('/delete_strategy', methods=['POST'])
def delete_strategy():
    strategy_name = request.json.get('name')
    strategies = load_user_strategies()
    strategies = [s for s in strategies if s['name'] != strategy_name]
    save_user_strategies(strategies)
    return jsonify({"message": "Strategy deleted successfully", "strategies": strategies})

@app.route('/check_strategy_name', methods=['POST'])
def check_strategy_name():
    name = request.json.get('name')
    strategies = load_user_strategies()
    exists = any(strategy['name'] == name for strategy in strategies)
    return jsonify({"exists": exists})

if __name__ == '__main__':
    app.run(debug=True)