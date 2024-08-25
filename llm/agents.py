import os
from typing import Dict, List

from dotenv import load_dotenv
import numpy as np
import pandas as pd


from openai import OpenAI

from .safe_executor import SafeExecutor

load_dotenv()

class CodeGeneratorAgent:
    def __init__(self, model: str = 'gpt-4o-mini'):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = model
        self.system_prompt = """
        You are an expert Python programmer specializing in data manipulation with pandas and implementing trading strategies. 
        Your task is to generate Python code based on the given description. Provide only the code without any explanation.
        
        The data you'll be working with is in a pandas DataFrame with the following columns:
        - dt: datetime (index)
        - open: float
        - high: float
        - low: float
        - close: float
        - volume: float
        
        The DataFrame represents data for a specific cryptocurrency and time frame, which have been filtered beforehand.
        Ensure that your code is compatible with this data structure.
        """

    def generate_code(self, task_description: str) -> str:
        """
        Generate Python code based on a task description.
        
        :param task_description: A string describing the code to be generated
        :return: Generated Python code as a string
        """
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"Generate Python code for the following task:\n\n{task_description}"}
        ]

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": "code_generation",
                            "strict": True,
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "code": {
                                        "type": "string"
                                    }
                                },
                                "required": ["code"],
                                "additionalProperties": False
                            }
                        }
                    }
                )

        return response.choices[0].message.content

    def refine_code(self, original_code: str, refinement_instructions: str) -> str:
        """
        Refine existing Python code based on new instructions.
        
        :param original_code: The original Python code as a string
        :param refinement_instructions: Instructions for refining the code
        :return: Refined Python code as a string
        """
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"Original code:\n\n{original_code}\n\nRefinement instructions:\n{refinement_instructions}"}
        ]

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": "code_generation",
                            "strict": True,
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "code": {
                                        "type": "string"
                                    }
                                },
                                "required": ["code"],
                                "additionalProperties": False
                            }
                        }
                    }
        )

        return response.choices[0].message.content
    
    def test_strategy(self, strategy_code: str, test_data: pd.DataFrame) -> pd.Series:
        """
        Test the generated strategy code using the SafeExecutor.
        
        :param strategy_code: The generated strategy code as a string
        :param test_data: A sample DataFrame to test the strategy
        :return: The signals generated by the strategy
        """
        executor = SafeExecutor()
        try:
            signals = executor.run_strategy(strategy_code, test_data)
            return signals
        except Exception as e:
            print(f"Error testing strategy: {str(e)}")
            return pd.Series()

# Example usage
if __name__ == "__main__":
    
    # Initialize the agent
    agent = CodeGeneratorAgent()

    # Generate DataframeManipulator class
    dataframe_manipulator_task = """
    Create a DataframeManipulator class with the following features:
    1. Initialize with a pandas DataFrame containing columns: dt (index), open, high, low, close, and volume
    2. Method to add Simple Moving Average (SMA) indicator for the 'close' price
    3. Method to add Relative Strength Index (RSI) indicator using the 'close' price
    4. Method to apply entry and exit conditions based on indicator values. 
    Ensure the class is flexible and can handle various parameter values.
    """
    dataframe_manipulator_code = agent.generate_code(dataframe_manipulator_task)

    # Generate strategy-specific code
    strategy_task = """
    Create a function that implements a Simple Moving Average crossover strategy with the following logic:
    1. Entry condition: When the fast SMA crosses above the slow SMA
    2. Exit condition: When the fast SMA crosses below the slow SMA
    3. Use the DataframeManipulator class to calculate SMAs and generate signals
    The function should return a pandas Series with buy signals (1), sell signals (-1), and hold (0).
    """
    strategy_code = agent.generate_code(strategy_task)

    # Refine the strategy code to include position sizing and risk management
    refinement_task = """
    Modify the strategy function to include:
    1. Position sizing: Use a fixed percentage of the account balance for each trade
    2. Stop loss: Implement a trailing stop loss at a fixed percentage below the entry price
    3. Take profit: Implement a take profit at a fixed percentage above the entry price
    4. Ensure that the function is optimized for performance with large datasets
    """
    refined_strategy_code = agent.refine_code(strategy_code, refinement_task)

    # Print the generated code
    print("DataframeManipulator Code:")
    print(dataframe_manipulator_code)

    print("\nStrategy Code:")
    print(refined_strategy_code)