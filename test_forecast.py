import traceback, sys
from forecast import run_forecasting_pipeline

try:
    res = run_forecasting_pipeline(horizon=3)
    print('Success')
    print(res['forecast_table'].head())
except Exception as e:
    print('Error:', e)
    traceback.print_exc()
