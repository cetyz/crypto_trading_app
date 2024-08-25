import pandas as pd
import os
from typing import List, Tuple

class DataHandler:
    def __init__(self, data_file: str):
        self.data_file = data_file
        self.df = None

    def load_csv(self) -> None:
        """
        Load the CSV data file.
        """
        if not os.path.exists(self.data_file):
            raise FileNotFoundError(f"Data file not found: {self.data_file}")
        
        self.df = pd.read_csv(self.data_file)
        self.df['dt'] = pd.to_datetime(self.df['dt'])
        self.df.set_index('dt', inplace=True)

    def get_data(self, token: str, time_frame: str) -> pd.DataFrame:
        """
        Retrieve data for a specific token and time frame.
        
        :param token: The cryptocurrency token (e.g., 'BTC', 'ETH')
        :param time_frame: The time frame of the data (e.g., '1d', '4h', '1h')
        :return: A pandas DataFrame with the filtered data
        """
        if self.df is None:
            raise ValueError("CSV file not loaded. Call load_csv() first.")
        
        filtered_df = self.df[(self.df['token'] == token) & (self.df['time_frame'] == time_frame)]
        if filtered_df.empty:
            raise ValueError(f"No data found for {token} with {time_frame} time frame")
        
        return filtered_df.drop(['token', 'time_frame'], axis=1)

    def validate_data(self, df: pd.DataFrame) -> Tuple[bool, List[str]]:
        """
        Validate the data for completeness and correctness.
        
        :param df: The DataFrame to validate
        :return: A tuple of (is_valid, error_messages)
        """
        errors = []
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        
        # Check for required columns
        missing_columns = set(required_columns) - set(df.columns)
        if missing_columns:
            errors.append(f"Missing required columns: {', '.join(missing_columns)}")
        
        # Check for missing values
        if df[required_columns].isnull().any().any():
            errors.append("Data contains missing values")
        
        # Check for negative values in volume
        if (df['volume'] < 0).any():
            errors.append("Negative values found in volume column")
        
        # Check for OHLC consistency
        if not ((df['low'] <= df['open']) & (df['low'] <= df['close']) & 
                (df['high'] >= df['open']) & (df['high'] >= df['close'])).all():
            errors.append("OHLC data is inconsistent")
        
        return len(errors) == 0, errors

    def get_available_tokens(self) -> List[str]:
        """
        Get a list of available tokens in the dataset.
        
        :return: A list of unique token names
        """
        if self.df is None:
            raise ValueError("CSV file not loaded. Call load_csv() first.")
        return self.df['token'].unique().tolist()

    def get_available_timeframes(self) -> List[str]:
        """
        Get a list of available time frames in the dataset.
        
        :return: A list of unique time frames
        """
        if self.df is None:
            raise ValueError("CSV file not loaded. Call load_csv() first.")
        return self.df['time_frame'].unique().tolist()

# Example usage
if __name__ == "__main__":
    data_handler = DataHandler("data\data.csv")
    data_handler.load_csv()
    
    print("Available tokens:", data_handler.get_available_tokens())
    print("Available time frames:", data_handler.get_available_timeframes())
    
    btc_daily = data_handler.get_data("BTC", "1d")
    is_valid, errors = data_handler.validate_data(btc_daily)
    if is_valid:
        print("Data is valid")
    else:
        print("Data validation errors:", errors)
    
    print(btc_daily.head())