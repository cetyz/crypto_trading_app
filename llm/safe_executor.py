import ast
import pandas as pd
import numpy as np
from typing import Any, Dict
import builtins
import textwrap

class SafeExecutor:
    def __init__(self):
        self.allowed_modules = {
            'pandas': pd,
            'numpy': np,
        }
        self.global_namespace = {
            '__builtins__': {
                name: getattr(builtins, name)
                for name in ['range', 'len', 'int', 'float', 'bool', 'str', 'list', 'dict', 'tuple', 'set', 'sum', 'min', 'max']
            },
            'pd': pd,
            'np': np,
        }
        self.local_namespace: Dict[str, Any] = {}

    def check_ast(self, code: str) -> bool:
        """
        Check if the AST of the code contains only allowed operations.
        """
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for n in node.names:
                    if n.name not in self.allowed_modules:
                        raise ValueError(f"Import of {n.name} is not allowed")
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr.startswith('__'):
                        raise ValueError(f"Use of dunder method {node.func.attr} is not allowed")
            elif isinstance(node, ast.Attribute):
                if node.attr.startswith('__'):
                    raise ValueError(f"Access to dunder attribute {node.attr} is not allowed")
        return True

    def execute(self, code: str, input_data: Dict[str, Any]) -> Any:
        """
        Safely execute the provided code with the given input data.
        """
        try:
            self.check_ast(code)
            self.local_namespace.update(input_data)
            exec(code, self.global_namespace, self.local_namespace)
            return self.local_namespace
        except Exception as e:
            raise RuntimeError(f"Error executing code: {str(e)}")

    def run_strategy(self, strategy_code: str, df: pd.DataFrame) -> pd.Series:
        """
        Run a trading strategy on the provided DataFrame.
        """
        input_data = {'df': df}
        result = self.execute(strategy_code, input_data)
        if 'signals' not in result:
            raise ValueError("Strategy code did not produce a 'signals' series")
        return result['signals']

# Example usage
if __name__ == "__main__":
    executor = SafeExecutor()
    
    # Example DataFrame
    df = pd.DataFrame({
        'close': [100, 101, 99, 102, 98, 103],
        'volume': [1000, 1100, 900, 1200, 950, 1300]
    }, index=pd.date_range(start='2023-01-01', periods=6))
    
    # Example strategy code
    strategy_code = textwrap.dedent("""
    def sma(data, window):
        return data.rolling(window=window).mean()
    
    df['SMA_short'] = sma(df['close'], 2)
    df['SMA_long'] = sma(df['close'], 4)
    
    signals = pd.Series(0, index=df.index)
    signals[df['SMA_short'] > df['SMA_long']] = 1
    signals[df['SMA_short'] < df['SMA_long']] = -1
    """)
    
    try:
        signals = executor.run_strategy(strategy_code, df)
        print("Generated signals:")
        print(signals)
    except Exception as e:
        print(f"Error: {str(e)}")