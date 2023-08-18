import pandas as pd
import os
import re # regex
import requests as reqs

SCHOOL_PROFILE_URL = "https://api.cps.edu/schoolprofile/CPS/"

#List of all employee position roster csv files
EPR_CSV_LIST = filter(lambda x: x.startswith("employeepositionroster"), os.listdir("data"))

# this formats all files the same way
# this was only needed for the 2014-2016 files and shouldn't be needed for 
# future years but I'm leaving it here (commented) just in case
"""
for file in EPR_CSV_LIST:
  df = pd.read_csv(f'data/{file}')
  #df.drop("Unnamed: 0", inplace=True, axis=1)
  df["Annual Salary"] = df["Annual Salary"].apply(lambda x: str(x).replace(",", ""))
  df["FTE Annual Salary"] = df["FTE Annual Salary"].apply(lambda x: str(x).replace(",", ""))
  df["Annual Benefit Cost"] = df["Annual Benefit Cost"].apply(lambda x: str(x).replace(",", ""))
  df.to_csv(f'data/{file}', index=False)
"""


def salary_report(df):
  """
  Takes in a dataframe representing part of an employee position roster.
  Returns a dict containing some useful datapoints about that dataframe.
  """
  df["Annual Salary"] = df["Annual Salary"].astype(float)
  df = df.dropna()
  df = df.sort_values("Annual Salary", ascending=False)
  # sort table by the annual salary of the employees
  return {
    "Average Salary": df["Annual Salary"].mean(),
    "Highest Salary": df["Annual Salary"].iat[0],
    "Highest Paid Position No.": df["Pos #"].iat[0],
    "Lowest Salary": df["Annual Salary"].iat[-1],
    "Lowest Paid Position No.": df["Pos #"].iat[-1]
  }

def get_salary(df, posno):
  """
  Returns the salary corresponding to the given position number
  Returns as a dict with "Salary": val for compatibility reasons
  """
  return {
    "Salary": df.loc[df["Pos #"] == posno]["Annual Salary"].iat[0]
  }

def filter(df, filters):
  """
  Filters a dataframe to only keep rows where the value in column {key} is equal
  to one of the values in { [value] }
  """
  outdf = df
  for (key, lst) in filters.items():
    outdf = outdf.loc[outdf[key].isin(lst)]
  return outdf

def all_years(fn, filters, *args):
  """
  Runs fn on all employee position rosters
  Returns a dictionary mapping the date of that roster to the result of the
  function
  """
  out = {}
  for df_name in EPR_CSV_LIST:
    df = pd.read_csv(f'data/{df_name}')
    if len(filters) > 0:
      df = filter(df, filters)
    date = re.split("[._]", df_name)[1]
    out[date] = fn(df, *args)
  return out

def flip_sort(dc):
  """
  Expects a dictionary where the values are also dictionaries.
  Switches the keys of the inner dictionaries to the outer ones and vice versa

  for example:
  {
    a: { foo: 1, bar: 3 },
    b: { foo: 5, bar: 2 }
  }
  becomes
  {
    foo: { a: 1, b: 5 },
    bar: { a: 3, b: 2 }
  }
  """
  first = True
  out = {}
  for key, dc2 in dc.items():
    for key2, val in dc2.items():
      if first: out[key2] = {}
      out[key2][key] = val
    first = False
  return out

def trends(dc):
  """
  Expects a dictionary whose keys are dates, specifically 20YY-06-30
  Only to be used internally, as a helper function for all_trends
  """
  out = {}
  lst = list(dc.keys())
  lst.sort()
  latest_date = lst[-1]
  print(latest_date)

  year = int(latest_date.split("-")[0])
  out["Current Value"] = round(dc[latest_date], 1)
  out["Last Year"] = round(dc[f'{year - 1}-06-30'], 1)
  out["5 Years Ago"] = round(dc[f'{year - 5}-06-30'], 1)

  delta1 = out["Current Value"] - out["Last Year"]
  pct1 = delta1 / out["Last Year"]
  pct1 = round(pct1 * 100, 1)

  out["Change since last year"] = f'{round(delta1, 1)} ({pct1}%)'

  delta2 = out["Current Value"] - out["5 Years Ago"]
  pct2 = delta2 / out["5 Years Ago"]
  pct2 = round(pct2 * 100, 1)

  out["Change over 5 years"] = f'{round(delta2, 1)} ({pct2}%)'

  sign2 = pct2 / abs(pct2) # the sign of the second percentage
  avg_of_five_year_rate = abs(pct2) ** 0.2
  avg_of_five_year_rate *= sign2

  avg_change = (avg_of_five_year_rate + pct1) / 2
  # the average of:
  #   the geometric mean of the 5 year rate of change and
  #   the one year rate of change

  next_value = out["Current Value"] * (avg_change/100 + 1)

  out["Projected Value Next Year"] = round(next_value, 1)

  return out

def all_trends(dc):
  """
  Expects a dict where keys are stats and values are dicts where
  keys are dates and values are the value for that stat

  Analyzes trends in the given data, such as rates of change
  """
  out = {}
  for key, dc2 in dc.items():
    out[key] = trends(dc2)
  return out

def analyze(fn, filters, *args):
  return all_trends(flip_sort(all_years(fn, filters, *args)))

def pretty_print_dict(dc):
  """
  Pretty prints a given dictionary, formatted as it would be coded
  """
  pretty_print_dict_r(dc, "dict", 2)

def pretty_print_dict_r(dc, prevkey, indent):
  """
  Recursive helper function for pretty_print_dict
  """
  print((" " * (indent - 2)) + prevkey + ": {")
  for (key, val) in dc.items():
    if type(val) is dict:
      pretty_print_dict_r(val, key, indent + 2)
    else:
      print((" " * indent) + key + ": " + str(val) + ",")
  print((" " * (indent - 2)) + "},")

def get_dept_id(school_id):
  """
  Given a school id, returns the corresponding department id, for use in
  querying the employee position roster data
  """
  res = reqs.get(f'{SCHOOL_PROFILE_URL}SingleSchoolProfile?SchoolID={school_id}')
  return res.json()["FinanceID"]

# Filters
TEACHERS = { "Job Title": [ "Regular Teacher" ] }
PRINCIPALS = { "Job Title": [ "Principal" ] }

def school_employees(school_id):
  """
  Returns a filter that will retrieve only employees at the provided school id
  """
  return { "Dept ID": [ get_dept_id(school_id) ] }

def combine_filters(*filters):
  """
  Combines multiple filter objects into one
  """
  out = {}
  for obj in filters:
    for key, val in obj.items():
      if key in out:
        out[key] += val
      else:
        out[key] = val
  pretty_print_dict(out)
  return out

pretty_print_dict(analyze(salary_report, combine_filters(school_employees(609755), TEACHERS)))