from binance.client import Client
import pandas as pd
import pandas_ta as ta
import ollama
import time
import schedule
from dotenv import load_dotenv
import os 

load_dotenv()

api_key = os.getenv('BINANCE_API_KEY_TEST')
api_secret = os.getenv('BINANCE_SECRET_KEY_TEST')

print(api_key)
print(api_secret)

client = Client(api_key, api_secret,testnet=True)

crypt = 'SEIUSDC'
preco_compra = None
quantidade_comprada = None
comprou = 0
vendeu = 0
qtd_ultima_vez_comprado = 0
qtd_ultima_vez_vendido = 0

# Exemplo: Pegar preço de mercado de um par
def pega_info_preco():
    preco_atual = client.get_symbol_ticker(symbol=crypt)['price']
    print(f"Preço Atual: {preco_atual}")

    info = client.get_symbol_info(crypt)
    step_size_symbol = info['filters'][1]['stepSize']
    print(f"Verificando tamanho de compra/venda {step_size_symbol}")
    return preco_atual,step_size_symbol

# Ajustar quantidade
def ajustar_quantidade(quantity, step_size):
    # Arredonda para a quantidade correta com base no step_size
    return round(quantity // float(step_size) * float(step_size), 8)


# Criação da IA
# def define_IA():
#     modelFile='''
#     from llama3.1
#     system You are a cryptocurrency trade assistant and you need to understand everything about cryptocurrencies, understand how to calculate whether the price will go up or down, to answer me whether I should sell or buy the crypto in question. To do this, use the data that I will send you as the value history data, these have 'close', 'volume', 'rsi', 'sma_20', 'ema_50', 'bollinger_upper', 'bollinger_middle', 'bollinger_lower' , 'macd_line', 'macd_signal', 'macd_hist', 'atr'. Use all this in your understanding. Just answer me with a Yes or No
#     '''
#     return ollama.create(model='binance_bot_2', modelfile=modelFile)

# # Função para obter dados históricos de preços (OHLCV)
def obter_historico(intervalo='5m', limite=50):
    print('Obtendo historico')
    klines = client.get_klines(symbol=crypt, interval=intervalo, limit=limite)
    df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'qav', 'num_trades', 'taker_base_vol', 'taker_quote_vol', 'ignore'])
    df['close'] = df['close'].astype(float)
    df['volume'] = df['volume'].astype(float)
    df['open'] = df['open'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    return df

# Função para obter saldo
def obter_saldo_crypt(asset):
    saldo = client.get_asset_balance(asset=asset)
    print(f"Saldo {asset}: {saldo['free']} {asset} (Disponível)")
    return saldo['free']

# Função para calcular indicadores usando pandas-ta
def calcular_indicadores(df):
    df['rsi'] = ta.rsi(df['close'], length=14)
    df['sma_20'] = ta.sma(df['close'], length=20)
    df['ema_50'] = ta.ema(df['close'], length=50)
    
    bb = ta.bbands(df['close'], length=20, std=2)
    
    df['bollinger_upper'] = bb['BBU_20_2.0']
    df['bollinger_middle'] = bb['BBM_20_2.0']
    df['bollinger_lower'] = bb['BBL_20_2.0']
    
    # Volume
    df['volume'] = df['volume']
    
    # MACD (12, 26, 9 são os períodos padrão)
    macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
    df['macd_line'] = macd['MACD_12_26_9']
    df['macd_signal'] = macd['MACDs_12_26_9']
    df['macd_hist'] = macd['MACDh_12_26_9']
    
    # ATR (Average True Range, usado para medir volatilidade)
    df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
    return df

def retorna_string_formatada():
    df = obter_historico()
    df_indicadores = calcular_indicadores(df)
    print('Formatando Indicadores')
    indicadores_str = ""
    for index, row in df_indicadores.iterrows():
        indicadores_str += (
            f"At time {row.name}, the indicators are:\n"
            f"- RSI: {row['rsi']:.2f}\n"
            f"- SMA 20: {row['sma_20']:.2f}\n"
            f"- EMA 50: {row['ema_50']:.2f}\n"
            f"- Bollinger Upper: {row['bollinger_upper']:.2f}\n"
            f"- Bollinger Middle: {row['bollinger_middle']:.2f}\n"
            f"- Bollinger Lower: {row['bollinger_lower']:.2f}\n"
            f"- Volume: {row['volume']:.2f}\n"
            f"- MACD Line: {row['macd_line']:.2f}\n"
            f"- MACD Signal: {row['macd_signal']:.2f}\n"
            f"- MACD Histogram: {row['macd_hist']:.2f}\n"
            f"- ATR: {row['atr']:.2f}\n\n"
        )
    return indicadores_str

# Mandando os indicadores para a IA
def obtem_resposta_IA(preco_atual):
    print('Iniciando pergunta')
    global comprou, vendeu, qtd_ultima_vez_comprado, qtd_ultima_vez_vendido
    indicadores_str = retorna_string_formatada()
    
    saldo = obter_saldo_crypt('SEI')
    saldo_usdc = obter_saldo_crypt('USDC')
    
    messages = [
        {
            'role':'system',
            'content': f"You are an advanced data analysis assistant. Your role is to analyze cryptocurrency market data and provide an output based on the historical information provided. This data includes fields such as 'close', 'volume', 'rsi', 'sma_20', 'ema_50', 'bollinger_upper', 'bollinger_middle', 'bollinger_lower', 'macd_line', 'macd_signal', 'macd_hist', and 'atr'. Based on this data, answer Yes or No to the following questions about market trends, using purely objective analysis from the data. You are not providing financial advice, only interpreting data patterns. Never say you can't answer and always respond with Yes or No, without explanations. My balance SEI is:{saldo} and USDC is: {saldo_usdc}, the current price is this:{preco_atual},last time I bought this:{qtd_ultima_vez_comprado} and I sold this: {qtd_ultima_vez_vendido}, if any value here is equal to 0, it means I didn't buy or sell, We have already bought: {comprou} and sold:{vendeu}, your job is to make me profit always"
        },
        # {
        #     'role':'user',
        #     'content': "You are a cryptocurrency trade assistant and you need to understand everything about cryptocurrencies, understand how to calculate whether the price will go up or down, to answer me whether I should sell or buy the crypto in question. To do this, use the data that I will send you as the value history data, these have 'close', 'volume', 'rsi', 'sma_20', 'ema_50', 'bollinger_upper', 'bollinger_middle', 'bollinger_lower' , 'macd_line', 'macd_signal', 'macd_hist', 'atr'. Use all this in your understanding. Just answer me with a Yes or No"
        # },
        # {
        #     'role':'user',
        #     'content': "never say that you can't give me financial tips or anything like that and remember to respond with Yes or No"
        # },
        {
            'role':'user',
            'content': f"indicators:{indicadores_str}"
        },
        # {
        #     'role':'user',
        #     'content': f"My balance SEI is:{saldo} and USDC is: {saldo_usdc}"
        # },
        # {
        #     'role':'user',
        #     'content': f"the current price is this:{preco_atual}"
        # },
        # {
        #     'role':'user',
        #     'content': f"last time I bought this:{qtd_ultima_vez_comprado} and I sold this: {qtd_ultima_vez_vendido}, if any value here is equal to 0, it means I didn't buy or sell"
        # },
        # {
        #     'role':'user',
        #     'content': f"We have already bought: {comprou} and sold:{vendeu}, your job is to make me profit always"
        # },
        {
            'role':'user',
            'content': f"Based on indicators, If you think I should buy, respond with 'Yes'. If you think I should sell, respond with 'No'. Provide no other information or explanation, just the word 'Yes' or 'No'."
        },
    ]
    print('Obtendo resposta IA')
    resposta = ollama.chat(model='llama3.1', messages=messages,keep_alive='0')
    return resposta['message']['content']

# Compra moeda
def comprar_mercado(symbol, quantidade,preco_atual):
    global comprou, vendeu, qtd_ultima_vez_comprado
    if comprou == 3 and vendeu == 0:
        print('Não vai comprar')
        return
    try:
        compra_agora = pega_info_preco()[0]
        print(f"Comprando agora há {compra_agora}")
        if compra_agora > preco_atual:
            diferenca = float(compra_agora) - float(preco_atual)
            print(f"Valor da compra agora é maior: {compra_agora} e a diferenca é {diferenca}")
            return
        ordem = client.order_market_buy(
            symbol=symbol,
            quantity=quantidade
        )
        print(f"Ordem de compra realizada: {ordem}")
        qtd_ultima_vez_comprado = quantidade
        comprou = comprou + 1
        if vendeu != 0:
            vendeu = vendeu - 1
        print(f' Na compra o comprou é: {comprou} e vendeu é: {vendeu}')
    except Exception as e:
        print(f"Erro ao realizar a ordem de compra: {e}")

# Função para realizar uma ordem de venda de mercado (Market Sell)
def vender_mercado(symbol, quantidade, preco_atual):
    global comprou, vendeu, qtd_ultima_vez_vendido
    if comprou == 0 and vendeu == 3:
        print('Não vai vender')
        return
    try:
        vendendo_agora = pega_info_preco()[0]
        print(f"Vendendo agora há {vendendo_agora}")
        if vendendo_agora > preco_atual:
            diferenca = float(vendendo_agora) - float(preco_atual)
            print(f"Valor da compra agora é maior: {vendendo_agora} e a diferenca é {diferenca}")
        ordem = client.order_market_sell(
            symbol=symbol,
            quantity=quantidade
        )
        print(f"Ordem de venda realizada: {ordem}")
        qtd_ultima_vez_vendido = quantidade
        vendeu = vendeu +1
        if comprou != 0:
            comprou = comprou -1
        print(f' Na venda o comprou é: {comprou} e vendeu é: {vendeu}')
    except Exception as e:
        print(f"Erro ao realizar a ordem de venda: {e}")

# Função para calcular lucro ou perda
def calcula_lucro_perda(compra_price, venda_price, quantidade):
    valor_compra = float(compra_price)
    valor_venda = float(venda_price)
    
    quantidade = float(quantidade)
    print(f"Comprei a {compra_price} e estou vendendo a {venda_price}")
    # Calculo de lucro ou perda
    lucro_ou_perda = (valor_venda - valor_compra) * quantidade
    return lucro_ou_perda

def main_bot():
    print("Iniciando processo")
    global preco_compra, quantidade_comprada, qtd_ultima_vez_comprado
    inicio = time.time()
    preco_atual,step_size_symbol = pega_info_preco()

    resposta_ia = obtem_resposta_IA(preco_atual)
    fim = time.time()
    print(f"Resposta da IA {resposta_ia}")
    
    if 'Yes' in resposta_ia :
        saldo_usdc = obter_saldo_crypt('USDC')
        
        valor_investido = float(saldo_usdc) * 0.8 # para comprar 80% 
        quantidade_compra = float(valor_investido) / float(preco_atual)
        quantidade_compra = ajustar_quantidade(quantidade_compra, step_size_symbol)
        print(f"Comprando {quantidade_compra} {crypt}")
        comprar_mercado(crypt,quantidade_compra,preco_atual)
        
        # Armazenar o preço de compra e a quantidade comprada
        preco_compra = preco_atual
        quantidade_comprada = quantidade_compra
    else:
        saldo_sei = obter_saldo_crypt('SEI')
        
        valor_venda = float(saldo_sei) * 1 # para vender tudo
        # valor_venda = float(saldo_sei) * 0.8
        valor_venda =  ajustar_quantidade(valor_venda, step_size_symbol)
        
        print (f"Vendendo {valor_venda} {crypt}")
        if float(qtd_ultima_vez_comprado) < float(valor_venda) and qtd_ultima_vez_comprado != 0:
            vender_mercado(crypt,valor_venda, preco_atual)
            preco_venda = preco_atual
            if preco_compra is not None and quantidade_comprada is not None:
                lucro_ou_perda = calcula_lucro_perda(preco_compra, preco_venda, quantidade_comprada)
                print(f"Lucro ou perda: ${lucro_ou_perda:.5f}")
        else:
            print('Nao vendeu pois a ultima compra foi maior')
    tempo_decorrido = fim - inicio
    print(f"Tempo de execução: {tempo_decorrido:.2f} segundos")
    return

main_bot()

schedule.every(2).minutes.do(main_bot)

# Loop para manter o agendador rodando
while True:
    
    schedule.run_pending()
    
    time.sleep(1)
