#!/usr/bin/python3

# Keep module imports prior to classes
import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
import sys
# import dataframe_image as dfi
# import df2img

import classes.Fetcher as Fetcher
import classes.ConfigManager as ConfigManager
from classes.OtaUpdater import OTAUpdater
from classes.Changelog import VERSION
import classes.Screener as Screener
import classes.Utility as Utility
from classes.ColorText import colorText
from classes.CandlePatterns import CandlePatterns
from classes.ParallelProcessing import StockConsumer
from classes.Utility import level3ReversalMenuDict, level3ChartPatternMenuDict
from classes.Changelog import VERSION
from alive_progress import alive_bar
import urllib
import numpy as np
import pandas as pd
from datetime import datetime
from time import sleep
from tabulate import tabulate
from Telegram import send_message, send_photo, send_document, initTelegram
import multiprocessing
multiprocessing.freeze_support()

# Try Fixing bug with this symbol
TEST_STKCODE = "SBIN"

# Constants
np.seterr(divide='ignore', invalid='ignore')

# Global Variabls
menuChoiceHierarchy = ''
defaultAnswer = None
screenCounter = None
screenResults = None
screenResultsCounter = None
stockDict = None
keyboardInterruptEvent = None
loadedStockData = False
loadCount = 0
maLength = None
newlyListedOnly = False

configManager = ConfigManager.tools()
fetcher = Fetcher.tools(configManager)
screener = Screener.tools(configManager)
candlePatterns = CandlePatterns()
level0MenuDict = {'X': 'Scanners', 'S': 'Strategies', 'B': 'Backtests'}
level1MenuDict = {'W': 'Screen stocks from my own Watchlist',
                  'N': 'Nifty Prediction using Artifical Intelligence (Use for Gap-Up/Gap-Down/BTST/STBT)',
                  'E': 'Live Index Scan : 5 EMA for Intraday',
                  '0': 'Screen stocks by the stock names (NSE Stock Code)',
                  '1': 'Nifty 50          ',
                  '2': 'Nifty Next 50     ',
                  '3': 'Nifty 100         ',
                  '4': 'Nifty 200         ',
                  '5': 'Nifty 500         ',
                  '6': 'Nifty Smallcap 50 ',
                  '7': 'Nifty Smallcap 100',
                  '8': 'Nifty Smallcap 250',
                  '9': 'Nifty Midcap 50   ',
                  '10': 'Nifty Midcap 100',
                  '11': 'Nifty Midcap 150',
                  '12': 'Nifty (All Stocks)',
                  '13': 'Newly Listed (IPOs in last 2 Year)        ',
                  '14': 'F&O Stocks Only'}
level2MenuDict = {'0': 'Full Screening (Shows Technical Parameters without any criterion)',
                  '1': 'Probable Breakouts              ',
                  '2': 'Recent Breakouts & Volumes',
                  '3': 'Consolidating stocks            ',
                  '4': 'Lowest Volume in last \'N\'-days (Early Breakout Detection)',
                  '5': 'RSI screening                   ',
                  '6': 'Reversal Signals',
                  '7': 'Stocks making Chart Patterns    ',
                  '8': 'CCI outside of the given range',
                  '9': 'Volume gainers                  ',
                  '10': 'Closing at least 2% up since last 3 days',
                  '11': 'Short term bullish stocks       ',
                  '12': '15 Minute Price & Volume breakout',
                  '13': 'Bullish RSI & MACD Intraday     ',
                  '14': 'NR4 Daily Today',
                  '15': '52 week low breakout            ',
                  '16': '10 days low breakout',
                  '17': '52 week high breakout           ',
                  '18': 'Bullish Aroon Crossover',
                  '19': 'MACD Historgram x below 0       ',
                  '20': 'RSI entering bullish territory',
                  '21': 'Bearish CCI crossover           ',
                  '22': 'RSI crosses above 30 and price higher than psar',
                  '23': 'Intraday Momentum Build-up      ',
                  '24': 'Extremely bullish daily close',
                  '25': 'Rising RSI                      ',
                  '26': 'Dividend Yield',
                  '42': 'Show Last Screened Results'
                  }
selectedChoice = {'0':'', '1':'','2':'','3':'','4':''}

def initExecution(menuOption=None):
    global selectedChoice, level0MenuDict
    Utility.tools.clearScreen()
    if menuOption == None:
        print(colorText.BOLD + colorText.WARN +
            '[+] Select a menu option:' + colorText.END)
        toggleText = 'T > Toggle between long-term (Default)' + colorText.WARN + ' [Current]'+ colorText.END + ' and Intraday user configuration\n' if not configManager.isIntradayConfig() else 'T > Toggle between long-term (Default) and Intraday' + colorText.WARN + ' [Current]' +  colorText.END + ' user configuration'
        menuText = ''
        for key in level0MenuDict:
            menuText = menuText + '\n     ' + key + ' > '+ level0MenuDict[key]
        print(colorText.BOLD + menuText + '''

    ''' + toggleText + '''
    E > Edit user configuration
    Y > View your user configuration

    U > Check for software update
    H > Help / About Developer
    Z > Exit (Ctrl + C)

    Enter your choice >  (default is ''' + colorText.WARN + 'X > Scanners) ''' + colorText.END
            )
    else:
        print('initExecution:menuOption:' + menuOption)
    try:
        if menuOption == None:
            menuOption = input(
                colorText.BOLD + colorText.FAIL + '[+] Select option: ')
            print(colorText.END, end='')
        if menuOption == '':
            menuOption = 'X'
        if not menuOption.isnumeric():
            menuOption = menuOption.upper()
            if menuOption == 'Z':
                input(colorText.BOLD + colorText.FAIL +
                    "[+] Press any key to Exit!" + colorText.END)
                sys.exit(0)
            elif menuOption in 'BHUTSEXY':
                Utility.tools.clearScreen()
                selectedChoice['0'] = menuOption
                return menuOption
    except KeyboardInterrupt:
        raise KeyboardInterrupt
    except Exception as e:
        showOptionErrorMessage()
        return initExecution()
    showOptionErrorMessage()
    return initExecution()

def showOptionErrorMessage():
    print(colorText.BOLD + colorText.FAIL +
              '\n[+] Please enter a valid option & try Again!' + colorText.END)
    sleep(2)
    Utility.tools.clearScreen()

def toggleUserConfig():
    configManager.toggleConfig()
    print(colorText.BOLD + colorText.GREEN +
    '\nConfiguration toggled to duration: ' + str(configManager.duration) + ' and period: ' + str(configManager.period) + colorText.END)
    input('\nPress any key to Continue...\n')

# Manage Execution flow
def initScannerExecution(tickerOption=None, executeOption=None):
    global newlyListedOnly, selectedChoice, level0MenuDict, level1MenuDict
    Utility.tools.clearScreen()
    print(colorText.BOLD + colorText.FAIL + '[+] You chose: ' + level0MenuDict[selectedChoice['0']].strip() + ' > ' + colorText.END)
    if tickerOption is None:
        print(colorText.BOLD + colorText.WARN +
            '[+] Select an Index for Screening:' + colorText.END)
        menuText = ''
        tabLevel = 0
        for key in level1MenuDict:
            if not key.isnumeric():
                menuText = menuText + '\n     ' + key + ' > '+ level1MenuDict[key]
            elif int(key) == 0:
                menuText = menuText + '\n\n     ' + key + ' > '+ level1MenuDict[key]
            else:
                spaces = '     ' if int(key) <= 9 else '    '
                if tabLevel == 0:
                    menuText = menuText + '\n' + spaces + key + ' > '+ level1MenuDict[key]
                elif tabLevel <= 2:
                    menuText = menuText + '\t' + key + ' > '+ level1MenuDict[key]
                tabLevel = tabLevel + 1
                if tabLevel >= 3:
                    tabLevel = 0

        print(colorText.BOLD + menuText + '''

    M > Back to the Top/Main menu
    Z > Exit

    Enter > ''' + colorText.WARN + 'All Stocks (default) ''' + colorText.END
            )
    try:
        if tickerOption is None:
            tickerOption = input(
                colorText.BOLD + colorText.FAIL + '[+] Select option: ')
            print(colorText.END, end='')
        if tickerOption == '' or tickerOption is None:
            tickerOption = 12
        # elif tickerOption == 'W' or tickerOption == 'w' or tickerOption == 'N' or tickerOption == 'n' or tickerOption == 'E' or tickerOption == 'e':
        elif not str(tickerOption).isnumeric():
            tickerOption = tickerOption.upper()
            if tickerOption in 'MENZ':
                return tickerOption, 0
        else:
            tickerOption = int(tickerOption)
            if(tickerOption < 0 or tickerOption > 14):
                raise ValueError
            elif tickerOption == 13:
                newlyListedOnly = True
                tickerOption = 12
        selectedChoice['1'] = str(tickerOption)
    except KeyboardInterrupt:
        raise KeyboardInterrupt
    except Exception as e:
        # raise e
        # import traceback
        # traceback.print_exc()
        print(colorText.BOLD + colorText.FAIL +
              '\n[+] Please enter a valid numeric option & Try Again!' + colorText.END)
        sleep(2)
        # input()
        Utility.tools.clearScreen()
        return initScannerExecution()
    if executeOption is None:
        if tickerOption and tickerOption != 'W':
            Utility.tools.clearScreen()
            print(colorText.BOLD + colorText.FAIL + '[+] You chose: ' + level0MenuDict[selectedChoice['0']].strip() + ' > ' + level1MenuDict[selectedChoice['1']].strip() + colorText.END)
            print(colorText.BOLD + colorText.WARN +
                '[+] Select a Criterion for Stock Screening: ' + colorText.END)
            menuText = ''
            tabLevel = 0
            for key in level2MenuDict:
                if int(key) == 0 or int(key) == 42:
                    spaces = '     ' if int(key) == 0 else '\n    '
                    menuText = menuText + '\n' + spaces + key + ' > '+ level2MenuDict[key]
                elif int(key) <= 26:
                    spaces = '     ' if int(key) <= 9 else '    '
                    if tabLevel == 0:
                        menuText = menuText + '\n' + spaces + key + ' > '+ level2MenuDict[key]
                    elif tabLevel == 1:
                        menuText = menuText + spaces + key + ' > '+ level2MenuDict[key]
                    tabLevel = tabLevel + 1
                    if tabLevel >= 2:
                        tabLevel = 0
            print(colorText.BOLD + menuText + '''

        M > Back to the Top/Main menu
        Z > Exit''' + colorText.END
                )
    try:
        if tickerOption and tickerOption != 'W':
            if executeOption is None:
                executeOption = input(
                    colorText.BOLD + colorText.FAIL + '[+] Select option: ')
                print(colorText.END, end='')
            if executeOption == '':
                executeOption = 0
            if not str(executeOption).isnumeric():
                executeOption = executeOption.upper()
            else:
                executeOption = int(executeOption)
                if(executeOption < 0 or executeOption > 44):
                    raise ValueError
        else:
            executeOption = 0
        selectedChoice['2'] = str(executeOption)
    except KeyboardInterrupt:
        raise KeyboardInterrupt
    except Exception as e:
        # raise e
        # import traceback
        # traceback.print_exc()
        print(colorText.BOLD + colorText.FAIL +
              '\n[+] Please enter a valid numeric option & Try Again!' + colorText.END)
        sleep(2)
        # input()
        Utility.tools.clearScreen()
        return initScannerExecution()
    return tickerOption, executeOption

# Main function
def main(testing=False, testBuild=False, downloadOnly=False, startupoptions=None, defaultConsoleAnswer=None):
    global screenResults, selectedChoice, level0MenuDict, level1MenuDict, level2MenuDict, defaultAnswer, menuChoiceHierarchy, screenCounter, screenResultsCounter, stockDict, loadedStockData, keyboardInterruptEvent, loadCount, maLength, newlyListedOnly
    defaultAnswer = defaultConsoleAnswer
    options = []
    screenCounter = multiprocessing.Value('i', 1)
    screenResultsCounter = multiprocessing.Value('i', 0)
    keyboardInterruptEvent = multiprocessing.Manager().Event()

    if stockDict is None:
        stockDict = multiprocessing.Manager().dict()
        loadCount = 0

    minRSI = 0
    maxRSI = 100
    insideBarToLookback = 7
    respChartPattern = 1
    daysForLowestVolume = 30
    reversalOption = None

    screenResults = pd.DataFrame(columns=[
                                 'Stock', 'Consolidating', 'Breaking-Out', 'LTP', 'Volume', 'MA-Signal', 'RSI', 'Trend', 'Pattern', 'CCI'])
    saveResults = pd.DataFrame(columns=[
                               'Stock', 'Consolidating', 'Breaking-Out', 'LTP', 'Volume', 'MA-Signal', 'RSI', 'Trend', 'Pattern', 'CCI'])

    
    if testBuild:
        tickerOption, executeOption = 1, 0
        selectedChoice = {'0':'X','1':'1','2':'0'}
    elif downloadOnly:
        exists, cache_file = Utility.tools.afterMarketStockDataExists()
        if exists:
            shouldReplace = Utility.tools.promptFileExists(cache_file=cache_file, defaultAnswer=defaultAnswer)
            if shouldReplace == 'N':
                print(cache_file + colorText.END + ' already exists. Exiting as user chose not to replace it!')
                sys.exit(0)
        tickerOption, executeOption = 12, 2
        selectedChoice = {'0':'X','1':'12','2':'2'}
    else:
        executeOption = None
        menuOption = None
        tickerOption = None
        try:
            if startupoptions is not None:
                options = startupoptions.split(':')
                menuOption = options[0] if len(options) >= 1 else None
                tickerOption = options[1] if len(options) >= 2 else None
                executeOption = options[2] if len(options) >= 3 else None
            menuOption = initExecution(menuOption=menuOption)
            if menuOption == 'H':
                Utility.tools.showDevInfo()
                main()
                return
            elif menuOption == 'U':
                OTAUpdater.checkForUpdate(getProxyServer(), VERSION)
                main()
                return
            elif menuOption == 'T':
                toggleUserConfig()
                main()
                return
            elif menuOption == 'E':
                configManager.setConfig(ConfigManager.parser)
                main()
                return
            elif menuOption == 'X':
                tickerOption, executeOption = initScannerExecution(tickerOption=tickerOption, executeOption=executeOption)
            elif menuOption == 'Y':
                configManager.showConfigFile()
                main()
                return
            else:
                print('Work in progress! Try selecting a different option.')
                sleep(3)
                main()
                return
        except KeyboardInterrupt:
            input(colorText.BOLD + colorText.FAIL +
                "[+] Press any key to Exit!" + colorText.END)
            sys.exit(0)

    if tickerOption == 'M' or executeOption == 'M':
        main()
        return
    if executeOption == 'Z':
        input(colorText.BOLD + colorText.FAIL +
              "[+] Press any key to Exit!" + colorText.END)
        sys.exit(0)
    
    volumeRatio = configManager.volumeRatio
    if executeOption == 4:
        try:
            daysForLowestVolume = int(input(colorText.BOLD + colorText.WARN +
                                            '\n[+] The Volume should be lowest since last how many candles? '))
        except ValueError:
            print(colorText.END)
            print(colorText.BOLD + colorText.FAIL +
                  '[+] Error: Non-numeric value entered! Screening aborted.' + colorText.END)
            input('')
            main()
            return
        print(colorText.END)
    if executeOption == 5:
        minRSI, maxRSI = Utility.tools.promptRSIValues()
        if (not minRSI and not maxRSI):
            print(colorText.BOLD + colorText.FAIL +
                  '\n[+] Error: Invalid values for RSI! Values should be in range of 0 to 100. Screening aborted.' + colorText.END)
            input('')
            main()
            return
    if executeOption == 6:
        if len(options) >= 4:
            reversalOption = int(options[3])
            if reversalOption == 4 or reversalOption == 6:
                if len(options) >= 5:
                    maLength = int(options[4])
                else:
                    reversalOption, maLength = Utility.tools.promptReversalScreening()
        else:
            reversalOption, maLength = Utility.tools.promptReversalScreening()
        if reversalOption is None or reversalOption == 0:
            main()
            return
        else:
            selectedChoice['3'] = str(reversalOption)
    if executeOption == 7:
        if len(options) >= 4:
            respChartPattern = int(options[3])
            selectedChoice['3'] = options[3]
            if respChartPattern in [1,2,3]:
                if len(options) >= 5:
                    insideBarToLookback = int(options[4])
                else:
                    respChartPattern, insideBarToLookback = Utility.tools.promptChartPatterns()
            elif respChartPattern in [0,4,5]:
                insideBarToLookback = 0
            else:
                respChartPattern, insideBarToLookback = Utility.tools.promptChartPatterns()
        if respChartPattern is None or insideBarToLookback is None:
            main()
            return
        else:
            selectedChoice['3'] = str(respChartPattern)
    if executeOption == 8:
        if len(options) >= 5:
            minRSI = int(options[3])
            maxRSI = int(options[4])
        else:
            minRSI, maxRSI = Utility.tools.promptCCIValues()
        if (not minRSI and not maxRSI):
            print(colorText.BOLD + colorText.FAIL +
                  '\n[+] Error: Invalid values for CCI! Values should be in range of -300 to 500. Screening aborted.' + colorText.END)
            input('')
            main()
            return
    if executeOption == 9:
        if len(options) >= 4:
            volumeRatio = float(options[3])
        else:
            volumeRatio = Utility.tools.promptVolumeMultiplier()
        if (volumeRatio <= 0):
            print(colorText.BOLD + colorText.FAIL +
                  '\n[+] Error: Invalid values for Volume Ratio! Value should be a positive number. Screening aborted.' + colorText.END)
            input('')
            main()
            return
        else:
            configManager.volumeRatio = float(volumeRatio)
    if executeOption == 42:
        Utility.tools.getLastScreenedResults()
        main()
        return
    if executeOption >= 15 and executeOption <= 39:
        print(colorText.BOLD + colorText.FAIL + '\n[+] Error: Option 15 to 39 Not implemented yet! Press any key to continue.' + colorText.END) 
        input('')
        main()
        return
    if (not str(tickerOption).isnumeric() and tickerOption in 'WEMNZ') or (str(tickerOption).isnumeric() and (tickerOption >= 0 and tickerOption < 15)):
        configManager.getConfig(ConfigManager.parser)
        try:
            if tickerOption == 'W':
                listStockCodes = fetcher.fetchWatchlist()
                if listStockCodes is None:
                    input(colorText.BOLD + colorText.FAIL +
                          f'[+] Create the watchlist.xlsx file in {os.getcwd()} and Restart the Program!' + colorText.END)
                    sys.exit(0)
            elif tickerOption == 'N':
                os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3' 
                prediction, pText, sText = screener.getNiftyPrediction(
                    data=fetcher.fetchLatestNiftyDaily(proxyServer=proxyServer), 
                    proxyServer=proxyServer
                )
                sendMessageToTelegramChannel(message=f'Nifty AI prediction for the next day: {pText}. {sText}')
                input('\nPress any key to Continue...\n')
                return
            elif tickerOption == 'M':
                main()
                return
            elif tickerOption == 'Z':
                input(colorText.BOLD + colorText.FAIL + "[+] Press any key to Exit!" + colorText.END)
                sys.exit(0)
            elif tickerOption == 'E':
                result_df = pd.DataFrame(columns=['Time','Stock/Index','Action','SL','Target','R:R'])
                last_signal = {}
                first_scan = True
                result_df = screener.monitorFiveEma(        # Dummy scan to avoid blank table on 1st scan
                        proxyServer=proxyServer,
                        fetcher=fetcher,
                        result_df=result_df,
                        last_signal=last_signal
                    )
                try:
                    while True:
                        Utility.tools.clearScreen()
                        last_result_len = len(result_df)
                        result_df = screener.monitorFiveEma(
                            proxyServer=proxyServer,
                            fetcher=fetcher,
                            result_df=result_df,
                            last_signal=last_signal
                        )
                        print(colorText.BOLD + colorText.WARN + '[+] 5-EMA : Live Intraday Scanner \t' + colorText.END + colorText.FAIL + f'Last Scanned: {datetime.now().strftime("%H:%M:%S")}\n' + colorText.END)
                        print(tabulate(result_df, headers='keys', tablefmt='psql'))
                        print('\nPress Ctrl+C to exit.')
                        if len(result_df) != last_result_len and not first_scan:
                            Utility.tools.alertSound(beeps=5)
                        sleep(60)
                        first_scan = False
                except KeyboardInterrupt:
                    input('\nPress any key to Continue...\n')
                    return
            else:
                if not downloadOnly:
                    menuChoiceHierarchy = f'({selectedChoice["0"]}) {level0MenuDict[selectedChoice["0"]].strip()} > ({selectedChoice["1"]}) {level1MenuDict[selectedChoice["1"]].strip()} > ({selectedChoice["2"]}) {level2MenuDict[selectedChoice["2"]].strip()}'
                    if selectedChoice['2'] == '6':
                        menuChoiceHierarchy = menuChoiceHierarchy + f' > ({selectedChoice["3"]}) {level3ReversalMenuDict[selectedChoice["3"]].strip()}'
                    elif selectedChoice['2'] == '7':
                        menuChoiceHierarchy = menuChoiceHierarchy + f' > ({selectedChoice["3"]}) {level3ChartPatternMenuDict[selectedChoice["3"]].strip()}'
                    print(colorText.BOLD + colorText.FAIL + '[+] You chose: ' + menuChoiceHierarchy + colorText.END)
                listStockCodes = fetcher.fetchStockCodes(tickerOption, proxyServer=proxyServer)
        except urllib.error.URLError:
            print(colorText.BOLD + colorText.FAIL +
                  "\n\n[+] Oops! It looks like you don't have an Internet connectivity at the moment! Press any key to exit!" + colorText.END)
            input('')
            sys.exit(0)

        if not downloadOnly and not Utility.tools.isTradingTime() and configManager.cacheEnabled and not loadedStockData and not testing:
            Utility.tools.loadStockData(stockDict, configManager, proxyServer, downloadOnly=downloadOnly, defaultAnswer=defaultAnswer)
            loadedStockData = True
        loadCount = len(stockDict)

        if not downloadOnly:
            print(colorText.BOLD + colorText.WARN +
                "[+] Starting Stock Screening.. Press Ctrl+C to stop!\n")
        else:
            print(colorText.BOLD + colorText.WARN +
                "[+] Starting download.. Press Ctrl+C to stop!\n")

        items = [(executeOption, reversalOption, maLength, daysForLowestVolume, minRSI, maxRSI, respChartPattern, insideBarToLookback, len(listStockCodes),
                  configManager, fetcher, screener, candlePatterns, stock, newlyListedOnly, downloadOnly, volumeRatio, testBuild)
                 for stock in listStockCodes]

        tasks_queue = multiprocessing.JoinableQueue()
        results_queue = multiprocessing.Queue()

        totalConsumers = multiprocessing.cpu_count()
        if totalConsumers == 1:
            totalConsumers = 2      # This is required for single core machine
        if configManager.cacheEnabled is True and multiprocessing.cpu_count() > 2:
            totalConsumers -= 1
        consumers = [StockConsumer(tasks_queue, results_queue, screenCounter, screenResultsCounter, stockDict, proxyServer, keyboardInterruptEvent)
                     for _ in range(totalConsumers)]

        for worker in consumers:
            worker.daemon = True
            worker.start()

        if testing or testBuild:
            for item in items:
                tasks_queue.put(item)
                result = results_queue.get()
                lstscreen = []
                lstsave = []
                if result is not None:
                    if result is not None:
                        lstscreen.append(result[0])
                        lstsave.append(result[1])
                    df_extendedscreen = pd.DataFrame(lstscreen, columns=screenResults.columns)
                    df_extendedsave = pd.DataFrame(lstsave, columns=saveResults.columns)
                    screenResults = pd.concat([screenResults, df_extendedscreen])
                    saveResults = pd.concat([saveResults, df_extendedsave])
                    if testing or (testBuild and len(screenResults) > 2):
                        break
        else:
            for item in items:
                tasks_queue.put(item)
            # Append exit signal for each process indicated by None
            for _ in range(multiprocessing.cpu_count()):
                tasks_queue.put(None)
            try:
                numStocks = len(listStockCodes)
                print(colorText.END+colorText.BOLD)
                bar, spinner = Utility.tools.getProgressbarStyle()
                
                with alive_bar(numStocks, bar=bar, spinner=spinner) as progressbar:
                    lstscreen = []
                    lstsave = []
                    while numStocks:
                        result = results_queue.get()
                        if result is not None:
                            lstscreen.append(result[0])
                            lstsave.append(result[1])
                        numStocks -= 1
                        progressbar.text(colorText.BOLD + colorText.GREEN +
                                         f'Found {screenResultsCounter.value} Stocks' + colorText.END)
                        progressbar()
                    # create extension
                    df_extendedscreen = pd.DataFrame(lstscreen, columns=screenResults.columns)
                    df_extendedsave = pd.DataFrame(lstsave, columns=saveResults.columns)
                    screenResults = pd.concat([screenResults, df_extendedscreen])
                    saveResults = pd.concat([saveResults, df_extendedsave])
                    # or columns= if identical columns
            except KeyboardInterrupt:
                try:
                    keyboardInterruptEvent.set()
                except KeyboardInterrupt:
                    pass
                print(colorText.BOLD + colorText.FAIL +
                      "\n[+] Terminating Script, Please wait..." + colorText.END)
                for worker in consumers:
                    worker.terminate()

        print(colorText.END)
        # Exit all processes. Without this, it threw error in next screening session
        for worker in consumers:
            try:
                worker.terminate()
            except OSError as e:
                if e.winerror == 5:
                    pass

        # Flush the queue so depending processes will end
        from queue import Empty
        while True:
            try:
                _ = tasks_queue.get(False)
            except Exception as e:
                break
        if not downloadOnly:
            # Publish to gSheet with https://github.com/burnash/gspread 
            screenResults.sort_values(by=['Volume'], ascending=False, inplace=True)
            saveResults.sort_values(by=['Volume'], ascending=False, inplace=True)
            screenResults.set_index('Stock', inplace=True)
            saveResults.set_index('Stock', inplace=True)
            screenResults.rename(
                columns={
                    'Trend': f'Trend ({configManager.daysToLookback}Periods)',
                    'Breaking-Out': f'Breakout ({configManager.daysToLookback}Periods)',
                    'LTP': 'LTP (% Chng)'
                },
                inplace=True
            )
            saveResults.rename(
                columns={
                    'Trend': f'Trend ({configManager.daysToLookback}Periods)',
                    'Breaking-Out': f'Breakout ({configManager.daysToLookback}Periods)',
                },
                inplace=True
            )
            Utility.tools.clearScreen()
            menuChoiceHierarchy = menuChoiceHierarchy + ' (Data Period: ' + configManager.period + ', Candle Duration: ' + configManager.duration + ')'
            print(colorText.BOLD + colorText.FAIL + '[+] You chose: ' + menuChoiceHierarchy + colorText.END)
            tabulated_results = tabulate(screenResults, headers='keys', tablefmt='psql')
            print(tabulated_results)
            if len(screenResults) >= 1:
                markdown_results = tabulate(saveResults, headers='keys', tablefmt='psql')
                pngName = 'PKScreener-result_' + \
                        datetime.now().strftime("%d-%m-%y_%H.%M.%S")+".png"
                Utility.tools.tableToImage(markdown_results,pngName,menuChoiceHierarchy)
                sendMessageToTelegramChannel(message=None, photo_filePath=pngName, caption=menuChoiceHierarchy)
                try:
                    os.remove(pngName)
                except:
                    pass
            print(colorText.BOLD + colorText.GREEN +
                    f"[+] Found {len(screenResults)} Stocks." + colorText.END)
        if downloadOnly or (configManager.cacheEnabled and not Utility.tools.isTradingTime() and not testing):
            print(colorText.BOLD + colorText.GREEN +
                  "[+] Caching Stock Data for future use, Please Wait... " + colorText.END, end='')
            Utility.tools.saveStockData(
                stockDict, configManager, loadCount)

        Utility.tools.setLastScreenedResults(screenResults)
        if not testBuild and not downloadOnly:
            if len(screenResults) >= 1:
                filename = Utility.tools.promptSaveResults(saveResults, defaultAnswer = defaultAnswer)
                if filename is not None:
                    sendMessageToTelegramChannel(document_filePath=filename, caption=menuChoiceHierarchy)
                print(colorText.BOLD + colorText.WARN +
                    "[+] Note: Trend calculation is based on number of days recent to screen as per your configuration." + colorText.END)
                try:
                    os.remove(filename)
                except:
                    pass
            print(colorText.BOLD + colorText.GREEN +
                "[+] Screening Completed! Press Enter to Continue.." + colorText.END)
            if defaultAnswer is not None and defaultAnswer.upper() != 'Y':
                input('')
        newlyListedOnly = False

def sendMessageToTelegramChannel(message=None,photo_filePath=None,document_filePath=None, caption=None):
    if message is not None:
        try:
            send_message(message)
        except:
            pass
    if photo_filePath is not None:
        try:
            send_photo(photo_filePath, caption)
        except:
            pass
    if document_filePath is not None:
        try:
            send_document(document_filePath, caption)
        except:
            pass

def getProxyServer():
    # Get system wide proxy for networking
    try:
        proxyServer = urllib.request.getproxies()['http']
    except KeyError:
        proxyServer = ""
    return proxyServer

proxyServer = getProxyServer()

# https://chartink.com/screener/15-min-price-volume-breakout
# https://chartink.com/screener/15min-volume-breakout
