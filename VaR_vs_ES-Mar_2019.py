 # -*- coding: utf-8 -*-
"""
Created on Fri Mar  8 19:30:24 2019

@author: nicholaserikdann
"""

####################################
#            LIBRARIES
####################################

import pandas as pd
import numpy as np
import pandas_datareader.data as web
import fix_yahoo_finance as fix
import datetime as dt
import sys
import re
import time
import requests
from bs4 import BeautifulSoup
import random
from matplotlib import pyplot as plt
import math

####################################
#        FUNCTIONS / CLASSES        
####################################


### Main Functions ###


def scrape_wiki(url):
    """Scrapes wikipedia url and returns a list of tickers (symbols) for index
    components
    ---------------------------------------------------------------------------
    inputs:
        url: str type world wide web address of the index's wikipedia page 
    outputs:
        list type array of all the tickers comprising the index
    ---------------------------------------------------------------------------
    """       
    website_url = requests.get(url).text
    soup = BeautifulSoup (website_url, 'lxml')
    table = soup.find('table', {'class' : 'wikitable sortable'})
    links = table.findAll('a')
    # obtain references from links
    links_2 = []    
    for l in links:
        links_2.append(l.get('href'))
    
    # split links
    split_links = []
    for l in links_2:
        split_links.append(l.split ("/"))
    
    # identify and group symbols in a list of tickers
    tickers = []
    for sl in split_links:
        try:    
            if sl[0] != '':
                if sl[2]=='www.nyse.com' or sl[2]=='www.nasdaq.com':
                    split = sl[4].split(":")
                    if len(split) > 1:
                        tickers.append(split[1])
                    else:
                        tickers.append(split[0].upper())
                else:
                    pass
            else:
                pass
        except IndexError:
            pass
    
    return tickers


def get_data(ticker):
    """ Creates Dataframe with market data for the provided ticker
    ---------------------------------------------------------------------------
    inputs:
        ticker: str type representing the security's symbol in the market
    outputs:
        df structure with relevant market data (Adjusted Close) for sessions 
        encompassed between start and end date
    ---------------------------------------------------------------------------
    """    
    start = dt.datetime(1989, 2, 1)
    end = dt.datetime(2019, 2, 1)
    data = web.DataReader (ticker, 'yahoo', start, end)
    a_close = data['Adj Close']
    
    return a_close


def series_reconstructor(df, reference='^DJI'):
    """Creates DataFrame structure, with filled missing values in time series.
    Data points are generated by backward replication of reference 
    index's returns
    ---------------------------------------------------------------------------
    inputs:
        df: DataFrame structure with all relevant market data
        reference: reference index whose returns will be replicated 
        (Dow Jones by default)
    outputs:
        Fully reconstructed (filled) DataFrame structure with relevant 
        market data
    ---------------------------------------------------------------------------
    """
    # locate series with missing values and store tickers in list
    incomplete_tickers = []
    for i in df.isnull().any().index:
        if df.isnull().any()[i]:
            incomplete_tickers.append(i)
        else:
            pass
    
    # create dataframe with incomplete series, reference index series 
    series = df[[reference]+incomplete_tickers]
    # generate delta series (index variations), convert to list
    # and revert the order to allow forward replication of values
    ref_delta = (
            np.log(series[reference])
            -np.log(series[reference].shift(1))
    ).shift(-1).tolist()
    ref_delta.reverse()
    
    # transform the original time series (including missing values) to list
    # and revert order
    # loop the original series values, if value exists append to new series
    # list, if its null, then divide the last value of the new series by
    # the reference index's return of that day, in order to obtain the previous
    # day's value for the series and append to new series
    # new series is then reverted again, replacing the original series
    for t in incomplete_tickers:
        orig_series = df[t].tolist()
        orig_series.reverse()
        reconstructed_series = []
        for delt, orig in zip(ref_delta, orig_series):
            if not math.isnan(orig):
                reconstructed_series.append(orig)
                ref = orig
            else:
                reconstructed_series.append(ref / (1+delt))
                ref = reconstructed_series[-1]                
        reconstructed_series.reverse()
        df[t] = reconstructed_series
    
    return df


def portfolio_generator(df, k=10, n=10):
    """Creates Dictionary of index portfolio and "k" n-stock (randomly picked)
    portfolios, including market data for every portfolio's constituents
    ---------------------------------------------------------------------------
    inputs:
        df: DataFrame structure with all relevant market data
        k: number of portfolios to generate (10 by default)
        n: number of stocks for each random portfolio (10 by default)
    outputs:
        Dictionary structure consisting of:
            keys:
                'portfolio_0': portfolio consisting solely of the index
                (as proxy for a fully-diversified portfolio)
                'portfolio_k': k portfolios consisting of n stocks 
                randomly picked from index's constituents
            values:
                market data for each constituent of each portfolio
    ---------------------------------------------------------------------------
    """    
    portfolio_dict = {}
    portfolio_dict['portfolio_0'] = df[index]
    for i in range(1, k+1):
        portfolio_dict['portfolio_{0}'.format(i)] = df[
            random.sample(tickers, n)
            ]
    
    return portfolio_dict


def delta_calculator(df, n=10):
    """Calculates DataFrame values' variation (deltas) for the provided window
    (lapsed period), as: logN of final value - LogN of initial value
    ---------------------------------------------------------------------------
    inputs:
        df: DataFrame structure with all relevant market data.
        n: number of days to generate variations based on (window)
    outputs:
        Dictionary structure consisting of market data variations for the 
        provided window
    ---------------------------------------------------------------------------
    """    
    df = np.log(df) - np.log(df).shift(n)
    df = df.dropna()
    return df

def scenario_identificator(df, window=500):
    """Creates DataFrame structure with scenario labels for each porfolio. 
    Scenario lables are generated based on the portfolio's return on a moving
    window, and said return's location in the historic portfolio's window 
    return distribution (assuming normality)
    ---------------------------------------------------------------------------
    inputs:
        df: DataFrame structure with all relevant P&L data (deltas) for each
        portfolio
        window: size of the window (number of days) to be analyzed 
        (500 by default - last two years)
    outputs:
        DataFrame structure consisting of scenario labels for each portfolio 
        and daily moving window:
            labels:
                1. 'Boom': window's return is beyond two positive standard 
                deviations from average returns - 2% of scenarios (approx)
                2. 'Positive': window's return is between one and two positive 
                standard deviations from average returns - 14% scenarios 
                (approx)
                3. 'Neutral': window's return is within one standard deviation
                (either positive or negative) from average returns - 68% 
                scenarios (approx)
                4. 'Negative': window's return is between one and two negative
                standard deviations from average returns - 14% scenarios 
                (approx)
                5. 'Stressed': window's return is beyond two negative standard 
                deviations from average returns - 2% of scenaarios (approx)
    ---------------------------------------------------------------------------
    """    
    df_2 = pd.DataFrame(index=df.index, columns=df.columns)  
    progress = progress_bar(len(df), fmt=progress_bar.full)
    print()
    print('Calculating historic protfolio average returns for each window')

    # for data points with sufficient past data to fill n-day window
    # obtain average return of each rolling n-day window in the series
    for i in range(len(df)):
        if i-window >= 0:
            df_2.loc[df_2.index[i]] = df[i-window : i].mean()
        else:
            pass
        progress.current += 1
        progress()
        time.sleep(0.1)
    progress.done()
    # obtain historical average n-day window returns for each portfolio
    # and define scenario thresholds based on historical dispersion measures 
    # for each portfolio
    df_2 = df_2.dropna()
    mean = df_2.mean()
    pos_th = mean + df_2.std()
    neg_th = mean - df_2.std()
    boom_th = mean + df_2.std()*2
    stress_th = mean - df_2.std()*2
    
    # label each day's n-day window scenario, in accordance with historical
    # return and thresholds defined for each portfolio
    return scenario_labeler(df_2, boom_th, pos_th, neg_th, stress_th)


def var_calculator(df, window=500):
    """Creates DataFrame structure with daily historic VaR values (with 99% 
    confidence) for each portfolio and each window
    ---------------------------------------------------------------------------
    inputs:
        df: DataFrame structure with all relevant P&L data (deltas) for each
        portfolio
        window: size of the window (number of days) to be analyzed 
        (500 by default - last two years)
    outputs:
        DataFrame structure consisting of daily historic VaR calculations at 
        99% confidence level for each portfolio
    ---------------------------------------------------------------------------
    """    
    var_df = pd.DataFrame(index=df.index[window :])
    progress = progress_bar(len(df.columns), fmt=progress_bar.full)
    print()
    print('Calculating historic VaR values for each portfolio')
    # calculate historical VaR for each porfolio, as the closest quantile to
    # the confidence level percentile
    for col in df.columns:
        df_2 = df[col]
        var_vector = []
        for i in range(len(df_2)):
            if i-window >= 0:
                var_vector.append(
                        df_2[i-window : i].sort_values(ascending=False)
                        [round(len(df_2[i-window : i])*0.99)]
                        )
            else:
                pass
        var_df[col] = var_vector
        progress.current += 1
        progress()
        time.sleep(0.1)
    progress.done()
    return var_df


def es_calculator(df, window=500):
    """Creates DataFrame structure with daily historic ES values (with 99% 
    confidence) for each portfolio and each window
    ---------------------------------------------------------------------------
    inputs:
        df: DataFrame structure with all relevant P&L data (deltas) for each
        portfolio
        window: size of the window (number of days) to be analyzed 
        (500 by default - last two years)
    outputs:
        DataFrame structure consisting of daily historic ES calculations at 
        99% confidence level for each portfolio
    ---------------------------------------------------------------------------
    """    
    es_df = pd.DataFrame(index=df.index[window :])
    progress = progress_bar(len(df.columns), fmt=progress_bar.full)
    print()
    print('Caluclating historic ES values for each portfolio')
    # calculate historical ES for each portfolio, as the average of all 
    # quantiles beyond the confidence level percentile
    for col in df.columns:
        df_2 = df[col]
        es_vector = []
        for i in range(len(df_2)):
            if i-window >= 0:
                es_vector.append(
                        df_2[i-window : i].sort_values(ascending=False)
                        [round(len(df_2[i-window : i])*0.99)+1:].mean()
                        )
            else:
                pass
        es_df[col] = es_vector
        progress.current += 1
        progress()
        time.sleep(0.1)
    progress.done()
    return es_df


def backtester(scenario_matrix, pl_matrix, var_matrix, es_matrix):
    """Creates 3-D DataFrame strucutre with relevant metrics for each 
    portfolio, in order to perform Back-test analysis for VaR and ES
    ---------------------------------------------------------------------------
    inputs:
        scenario_matrix:
            DataFrame structure with daily scenario lables for each porftolio
        PL_matrix:
            DataFrame structure with daily P&L data (deltas) for each portfolio
        var_matrix:
            DataFrame structure with daily VaR calculations for each portfolio
        es_matrix:
            DataFrame structure with daily ES calculations for each portfolio
    outputs:
        DataFrame structure consisting of 3 dimensions:
            1. Timesteps: each portfolio's historical series for each metric
            2. Metrics:
                2.1. 'Scenario': daily scenario label for the portfolio
                2.2. 'P&L': daily n-day window return for the portfolio
                2.3. 'VaR': daily VaR calculation for the portfolio
                2.4. 'ES': daily ES calculation for the portfolio
                2.5. 'VaR - Back-test': historic daily boolean series where:
                    'True': P&L value is inferior to VaR value (VaR KO)
                    'False': P&L value is superior to VaR value (VaR OK)
                2.6. 'ES - Back-test': historic daily boolean series where:
                    'True': P&L value is inferior to ES value (ES KO)
                    'False': P&L value is superior to ES value (ES OK)
            3. Portfolios: each portfolio is back-tested indivdually
    ---------------------------------------------------------------------------
    """    
    idx = scenario_matrix.index
    lvl_1 = scenario_matrix.columns
    cube = pd.DataFrame(index=idx, columns=pd.MultiIndex.from_product(
            [lvl_1, 
             ['Scenario',
              'P&L',
              'VaR',
              'ES', 
              'VaR - Back-test',
              'ES - Back-test'
              ]
             ]
            )
    )
            
    for portfolio in lvl_1:
        table = pd.DataFrame()
        table['Scenario'] = scenario_matrix[portfolio]
        table['P&L'] = pl_matrix.loc[table.index, portfolio]
        table['VaR'] = var_matrix[portfolio]
        table['ES'] = es_matrix[portfolio]
        table['VaR - Back-test'] = table['VaR'] < table['P&L']
        table['ES - Back-test'] = table['ES'] < table['P&L']
        cube[portfolio] = table
    return cube


def results_summary(cube):
    """Creates 3-D DataFrame strucutre with relevant KPI summary regarding 
    metrics' back-test and performance analysis for VaR and ES
    ---------------------------------------------------------------------------
    inputs:
        cube: 3-D DataFrame structure consisting of a table (DataFrame) 
        structure with historic metric calculations and performance
        for each portfolio
    outputs:
        DataFrame structure consisting of 3 dimensions:
            1. KPIs:
                1.1. '% KOs - VaR': Ratio between number of KO days for VaR
                and total observations
                1.2. '%KOs - ES': Ratio between number of KO days for ES
                and total observations
                1.3. 'Max Period KO - VaR': Maximum number of consecutive 
                KO days for VaR
                1.4. 'Max Period KO - ES': Maximum number of consecutive 
                KO days for ES
                1.5. 'Max Excess Loss - VaR: Maximum loss incurred in excess 
                of VaR
                1.6. 'Max Excess Loss - ES': Maximum loss incurred in excess 
                of ES
            2. Scenarios: KPIs are calculated for each scenario
            ('Boom', 'Positive', 'Neutral', 'Negative' and 'Stressed')
            3. Portfolios: each portfolio summarized individually
    ---------------------------------------------------------------------------
    """    
    matrix = pd.DataFrame(
            index=['% KOs - VaR',
                '% KOs - ES',
                'Max Period KO - VaR',
                'Max Period KO - ES',
                'Max Excess Loss - VaR', 
                'Max Excess Loss - ES'
            ],
            columns=pd.MultiIndex.from_product(
                [cube.columns.levels[0],
                 ['Boom','Positive','Neutral','Negative','Stressed']
            ]
            )
    )
            
    progress = progress_bar(len(cube.columns.levels[0]), fmt=progress_bar.full)
    print()
    print('Summarizing back-test results for each portfolio')
    # for each portfolio
    for p in cube.columns.levels[0]:
        table = pd.DataFrame(
                index=['% KOs - VaR',
                       '% KOs - ES', 
                       'Max Period KO - VaR', 
                       'Max Period KO - ES',
                       'Max Excess Loss - VaR', 
                       'Max Excess Loss - ES'
                ],
                columns=['Boom',
                         'Positive', 
                         'Neutral', 
                         'Negative', 
                         'Stressed'
                ]
        )
        
        # calculate maximum consecutive KO periods for each portfolio
        # mapped with scenario type and store in dataframe
        ko_periods = cube[p].drop(['P&L', 'VaR', 'ES'], axis=1)
        ko_periods['VaR - Back-test'] = ko_period_calculator(
                ko_periods['VaR - Back-test']
        )
        ko_periods['ES - Back-test'] = ko_period_calculator(
                ko_periods['ES - Back-test']
        )
        ko_periods = ko_periods.groupby('Scenario').max()

        # for each scenario
        for col in table.columns:
            # filter result metrics by scenario type and store in temporary 
            # dataframe
            var_report = cube[p].where(
                    cube[p, 'VaR - Back-test'] == False
            ).dropna().where(cube[p, 'Scenario'] == col).dropna()
            es_report=cube[p].where(
                    cube[p, 'ES - Back-test'] == False
            ).dropna().where(cube[p, 'Scenario'] == col).dropna()
            # store metric results obtained in report table
            table.loc['% KOs - VaR', col] = var_report.count().max() / len(
                    cube[p]
            )*100
            table.loc['% KOs - ES', col] = es_report.count().max() / len(
                    cube[p]
            )*100
            table.loc['Max Excess Loss - VaR', col] = (
                    var_report['P&L'] - var_report['VaR']
            ).min()
            table.loc['Max Excess Loss - ES', col] = (
                    es_report['P&L'] - es_report['ES']
            ).min()
            # store maximum KO periods in report table for for scenarios in 
            # contained in KO period report (KO count > 0 either for VaR or ES)
            if col in ko_periods.index:
                table.loc['Max Period KO - VaR', col] = ko_periods.loc[col,
                         'VaR - Back-test'
                ]
                table.loc['Max Period KO - ES', col] = ko_periods.loc[col, 
                         'ES - Back-test'
                ]
            else:
                pass
        matrix[p] = table
        progress.current += 1
        progress()
        time.sleep(0.1)
    progress.done()
    return matrix


### Support Functions ###

def scenario_labeler(df, boom_thresholds, pos_thresholds, 
                     neg_thresholds, stress_thresholds):
    """Implements logic for scenario labeling based on portfolio's historic 
    returns and defined thresholds for scenario types
    ---------------------------------------------------------------------------
    inputs:
        df: DataFrame structure with portfolio's historic n-day window returns
        boom_thresholds: DataFrame structure with threshold values for 
        'Boom' scenarios, for each portfolio
        pos_thresholds: DataFrame structure with threshold values for 
        'Positive' scenarios, for each portfolio
        neg_thresholds: DataFrame structure with threshold values for 
        'Negative' scenarios, for each portfolio
        stress_thresholds: DataFrame structure with threshold values for 
        'Stressed' scenarios, for each portfolio
    outputs:
        DataFrame structure consisting of scenario labels for each portfolio 
        and daily moving window:
            labels:
                1. 'Boom': window's return is beyond two positive standard 
                deviations from average returns - 2% of scenaarios (approx)
                2. 'Positive': window's return is between one and two positive 
                standard deviations from average returns - 14% scenarios 
                (approx)
                3. 'Neutral': window's return is within one standard deviation
                (either positive or negative) from average returns - 68% 
                scenarios (approx)
                4. 'Negative': window's return is between one and two negative
                standard deviations from average returns - 14% scenarios 
                (approx)
                5. 'Stressed': window's return is beyond two negative standard 
                deviations from average returns - 2% of scenaarios (approx)
    ---------------------------------------------------------------------------
    """    
    progress = progress_bar(len(df.columns), fmt=progress_bar.full)
    print()
    print ('Classifying historic scenarios for each portfolio')    
    labels = pd.DataFrame(index=df.index, columns=df.columns)
    # for each portfolio, define scenario type threshold and implement 
    # scenario label logic
    for p in labels.columns:
        boom = boom_thresholds[p]
        pos = pos_thresholds[p]
        neg = neg_thresholds[p]
        strs = stress_thresholds[p]
        for i in labels.index:
            val = df.loc[i, p]
            if val >= boom:
                labels.loc[i, p] = 'Boom'
            elif val >= pos:
                labels.loc[i, p] = 'Positive'
            elif val <= strs:
                labels.loc[i, p] = 'Stressed'
            elif val <= neg:
                labels.loc[i, p] = 'Negative'
            else:
                labels.loc[i, p] = 'Neutral'
        progress.current += 1
        progress()
        time.sleep(0.1)
    progress.done()
    return labels


def ko_period_calculator(series):
    """Calculates number of consecutive KO days for metric
    ---------------------------------------------------------------------------
    inputs:
        series: vector of boolean values consisting of metric's back-test, 
        where:
            1. 'True': P&L value is inferior to metric value (metric KO)
            2. 'False': P&L value is superior to metric value (metric OK)
    outputs:
        List structure with consecutive KO values
    ---------------------------------------------------------------------------
    """
    series=series.tolist()
    val=0
    vector = []
    # store count of consecutive KO in list
    for i in series:
        if i is False:
            val += 1
        else:
            val = 0
        vector.append(val)
    return vector

        
### Classess ###


class progress_bar(object):
    """Object to provide visual aid to user, as a representation of current 
    process status
    """
    default = 'Progress: %(bar)s %(percent)3d%%'
    full = '%(bar)s %(current)d/%(total)d (%(percent)3d%%) %(remaining)d to go'
    
    def __init__(self, total, width=40, fmt=default, 
                 symbol='=', output=sys.stderr):
        assert len(symbol) == 1
        
        self.total = total
        self.width = width
        self.symbol = symbol
        self.output = output
        self.fmt = re.sub(
                r'(?P<name>%\(.+?\))d', r'\g<name>%dd' % len(str(total)), fmt
        )
        self.current = 0
        
    def __call__(self):
        percent = self.current / float(self.total)
        size = int(self.width * percent)
        remaining = self.total - self.current
        bar = '[' + self.symbol*size + ' '*(self.width-size) + ']'
        args = {'total':self.total,
              'bar':bar,
              'current':self.current,
              'percent':percent*100,
              'remaining': remaining
        }
        print( '\r' + self.fmt%args, file=self.output, end='')
    
    def done(self):
        self.current = self.total
        self()
        print('', file=self.output)
        
####################################
#             MAIN CODE
####################################

if __name__ == "__main__":
    
    print('Volatility and Risk - '
          'Value-at-Risk (VaR) vs Expected Shortfall (ES)'
          )
    print()
    
    # scrape wikipedia for tickers
    url = 'https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average'
    tickers = scrape_wiki(url)
    
    # yahoo finance override
    fix.pdr_override ()
    
    # define index and get market data
    index = '^DJI' # Dow Jones Idustrial Average Index
    loaded_tickers = []
    data = pd.DataFrame(columns=[index]+tickers)
    progress = progress_bar(len(data.columns), fmt=progress_bar.full)
    print('Loading Market Data')
    while len(data.columns) > len(loaded_tickers):
        for col in data.columns:
            if col not in loaded_tickers:
                try:
                    data[col] = get_data(col)
                    loaded_tickers.append(col)
                    progress.current += 1
                    progress()
                    time.sleep(0.1)
                except Exception as e:
                    pass
    progress.done()
    
    # series reconstruction
    data = series_reconstructor(data)

    # generate random portfolios
    portfolios = portfolio_generator(data)
        
    # calculate historic P&L vectors for each portfolio
    hist_pl = pd.DataFrame(columns=portfolios.keys())
    for p in portfolios.keys():
        if p != 'portfolio_0':
            hist_pl[p] = delta_calculator(portfolios[p]).mean(axis=1)
        else:
            hist_pl[p] = delta_calculator(portfolios[p])
    
    # identify scenarios
    scenarios = scenario_identificator(hist_pl)
    
    # implement VaR for each portfolio
    var = var_calculator(hist_pl)
    
    # implement ES for each portfolio
    es = es_calculator(hist_pl)
    
    # back-test strategies
    metrics = backtester(scenarios, hist_pl, var, es)
    
    # summarize results
    summary = results_summary(metrics)
    print()
    print('Summarized results of VaR and ES back-testing:')
    for p in summary.columns.levels[0]:
        print()
        print(p)
        print(summary[p])

    for i in summary.index:
        plt.figure()
        for p in summary.columns.levels[0]:
            summary.loc[i, p].plot(label=p)
        plt.title(i)
        plt.legend()
        plt.show()
