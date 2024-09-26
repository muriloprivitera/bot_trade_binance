from binance.client import Client
import pandas as pd
import pandas_ta as ta
import time
import schedule
from dotenv import load_dotenv
import os 
from datetime import datetime

#Amanha verificar se tem um maximo para comprar/vender; Verificar se sempre ao iniciar esta vendendo se sim bloquear isso(so voltar != 0); Criar um arquivo txt em toda operação tendo valor inicial antes de tudo das duas moedas, valor da compra/venda, e o lucro sempre q vender

load_dotenv()

api_key = os.getenv('BINANCE_API_KEY')
api_secret = os.getenv('BINANCE_SECRET_KEY')
# timestamp_millis = int(1000*(datetime.utcnow() - datetime.utcfromtimestamp(0)).total_seconds())
client = Client(api_key, api_secret)

crypt = 'ETHBRL'
preco_compra = 0.0
ordem_compra = None
ordem_venda = None
preco_venda = 0.0
preco_venda_verdadeiro = 0.0
quantidade_comprada = 0.0
quantidade_comprada_verdadeiro = 0.0
comprou = 0
vendeu = 0
ultimo_valor = 0.0
rsi_anterior = None
nome_arquivo_final = ''
trade_fee = client.get_trade_fee(symbol='ETHBRL')
print(trade_fee)
#Função para criar um txt com informações
def criar_arquivo_saldo(saldo_inicial,saldo_final,lucro_perda,cripto):
    global nome_arquivo_final
    data_atual = datetime.now().strftime('%Y-%m-%d')
    nome_arquivo = f"saldoFinal_{data_atual}.txt"
    nome_arquivo_final =  os.path.join("registros_saldo", nome_arquivo)
    diretorio = "registros_saldo"
    hora_atual = datetime.now().strftime('%H:%M:%S')
    if not os.path.exists(diretorio):
        os.makedirs(diretorio)
    
    caminho_arquivo = os.path.join(diretorio, nome_arquivo)
    
    if os.path.exists(caminho_arquivo):
        modo_abertura = 'a'
    else:
        modo_abertura = 'w'
    
    with open(caminho_arquivo, modo_abertura) as arquivo:
        if modo_abertura == 'w':
            arquivo.write("Relatório diário\n")
            arquivo.write(f"Data: {data_atual}\n")
        arquivo.write(f"{hora_atual} - Saldo inicial: {saldo_inicial} {cripto}\n")
        arquivo.write(f"{hora_atual} - Saldo final: {saldo_final} {cripto}\n")
        arquivo.write(f"{hora_atual} - Valores/Quantidade: ${lucro_perda} \n")
        arquivo.write("\n")
    return

# Função para adicionar uma linha ao log txt
def adicionar_linha_ao_arquivo(linha):
    global nome_arquivo_final
    data_atual = datetime.now().strftime('%Y-%m-%d')
    hora_atual = datetime.now().strftime('%H:%M:%S')
    if nome_arquivo_final == '':
        nome_arquivo_final = os.path.join("registros_saldo", f"saldoFinal_{data_atual}.txt")

    if not os.path.exists(nome_arquivo_final):
        with open(nome_arquivo_final, 'w') as file:
            file.write("Relatório diário\n")
            file.write(f"Data: {data_atual}\n")
    with open(nome_arquivo_final, 'a') as file:
        file.write(hora_atual + ' - ' + linha + '\n')

# Exemplo: Pegar preço de mercado de um par
def pega_info_preco():
    preco_atual = client.get_symbol_ticker(symbol=crypt)['price']
    
    adicionar_linha_ao_arquivo(f"Preço Atual: {preco_atual}")
    
    info = client.get_symbol_info(crypt)
    
    step_size_symbol = info['filters'][1]['stepSize']
    return preco_atual,step_size_symbol

def obter_historico(intervalo='1m', limite=50):
    klines = client.get_klines(symbol=crypt, interval=intervalo, limit=limite)
    df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'qav', 'num_trades', 'taker_base_vol', 'taker_quote_vol', 'ignore'])
    df['close'] = df['close'].astype(float)
    df['volume'] = df['volume'].astype(float)
    df['open'] = df['open'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    # df['MACD'] = df['MACD'].astype(float)
    # df['MACD_signal'] = df['MACD_signal'].astype(float)
    return df

def calcular_indicadores(df):
    df['rsi'] = ta.rsi(df['close'], length=14)
    df['sma_20'] = ta.sma(df['close'], length=20)
    df['ema_50'] = ta.ema(df['close'], length=50)
    df['ema_9'] = ta.ema(df['close'], length=9)
    df['ema_21'] = ta.ema(df['close'], length=21)
    
    # df['VWAP'] = ta.vwap(df['high'], df['low'], df['close'], df['volume'])
    bb = ta.bbands(df['close'], length=20, std=2)
    
    df['bollinger_upper'] = bb['BBU_20_2.0']
    df['bollinger_middle'] = bb['BBM_20_2.0']
    df['bollinger_lower'] = bb['BBL_20_2.0']
    
    # Volume
    df['volume'] = df['volume']
    
    # MACD (12, 26, 9 sÃ£o os perÃ­odos padrÃ£o)
    macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
    df['macd_line'] = macd['MACD_12_26_9']
    df['macd_signal'] = macd['MACDs_12_26_9']
    df['macd_hist'] = macd['MACDh_12_26_9']
    
    # ATR (Average True Range, usado para medir volatilidade)
    df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
    df.dropna(inplace=True)
    return df
# Ajustar quantidade
def ajustar_quantidade(quantity, step_size):
    # Arredonda para a quantidade correta com base no step_size
    # print(step_size)
    # print(float(quantity) // float(step_size) * float(step_size), 8)
    return round(float(quantity) // float(step_size) * float(step_size), 8)

# Função para obter saldo
def obter_saldo_crypt(asset):
    saldo = client.get_asset_balance(asset=asset,recvWindow=10000)
    return saldo['free']

# Compra moeda
def comprar_mercado(symbol, quantidade,compra_agora,tentativas=3):
    global comprou, vendeu,ordem_compra,preco_compra,preco_venda

    tentativa_atual = 0
    while tentativa_atual <= tentativas:
        try:
            saldo_usdc = obter_saldo_crypt('BRL')
            print(f"Saldo BRL: {saldo_usdc} BRL (Disponível) na Compra")
            
            saldo_sei = obter_saldo_crypt('ETH')
            print(f"Saldo ETH: {saldo_sei} ETH (Disponível) na Compra")
            
            ordem = client.order_limit_buy(
                symbol=symbol,
                quantity=quantidade,
                price=compra_agora,
                timeInForce='IOC',
                recvWindow=10000
            )
            print(ordem)
            if float(ordem['executedQty']) == 0.0:
                # preco_compra = 0.0
                adicionar_linha_ao_arquivo(f"Ordem de compra nao realizada pois é zero: {ordem['executedQty']}")
                tentativa_atual += 1
                time.sleep(1)
                continue  # Tentar novamente
            print(f"Ordem de compra realizada: {ordem}")
            valores_investidos = calcular_compra_venda(ordem)
            ordem_compra = valores_investidos
            # valor_investido = float(ordem['executedQty']) * float(ordem['price'])
            adicionar_linha_ao_arquivo(f"Ordem de compra realizada: {ordem} no valor {valores_investidos['total_gasto']} e quantidade {valores_investidos['total_quantidade_comprada']}")
            comprou = comprou + 1
            
            saldo_usdc_pos = obter_saldo_crypt('BRL')
            print(f"Saldo BRL: {saldo_usdc_pos} BRL (Disponível) Pos compra")
            
            saldo_sei_pos = obter_saldo_crypt('ETH')
            print(f"Saldo ETH: {saldo_sei_pos} ETH (Disponível) Pos compra")
            criar_arquivo_saldo(saldo_usdc,saldo_usdc_pos,f'Gastei {valores_investidos['total_gasto']}' ,'BRL')
            
            criar_arquivo_saldo(saldo_sei,saldo_sei_pos,f'Para Comprar {valores_investidos['total_quantidade_comprada']}','ETH')
            
            print(f' Na compra o comprou é: {comprou} e vendeu é: {vendeu}')
            return True
        except Exception as e:
            # preco_compra = 0.0
            print(f"Erro ao realizar a ordem de compra: {e}")
            return False
        return False

# Função para realizar uma ordem de venda de mercado (Market Sell)
def vender_mercado(symbol, quantidade,vendendo_agora,tentativas=3):
    global comprou, vendeu,preco_venda,ordem_venda
    tentativa_atual = 0
    while tentativa_atual <= tentativas:
        try:
            saldo_sei = obter_saldo_crypt('ETH')
            if float(saldo_sei) < 0.0001000000:
                adicionar_linha_ao_arquivo(f"Não vendeu pois o saldo é menor do que o permitido: {saldo_sei}")
                return False
            print(f"Saldo ETH: {saldo_sei} ETH (Disponível) na Venda")
            saldo_usdc = obter_saldo_crypt('BRL')
            print(f"Saldo BRL: {saldo_usdc} BRL (Disponível) na Venda")
            ordem = client.order_limit_sell(
                symbol=symbol,
                quantity=quantidade,
                price=vendendo_agora,
                timeInForce='IOC',
                recvWindow=10000
            )
            print(ordem)
            if float(ordem['executedQty']) == 0:
                # preco_venda = 0.0
                adicionar_linha_ao_arquivo(f"Ordem de venda nao realizada pois é zero: {ordem['executedQty']}")
                tentativa_atual += 1
                time.sleep(1)
                continue  # Tentar novamente
            print(f"Ordem de venda realizada: {ordem}")
            valores_ganhos = calcular_compra_venda(ordem)
            ordem_venda = valores_ganhos
            adicionar_linha_ao_arquivo(f"Ordem de venda realizada: {ordem} no valor {valores_ganhos['total_ganho']} e quantidade vendida {valores_ganhos['total_quantidade_vendida']}")
            saldo_usdc_pos = obter_saldo_crypt('BRL')
            print(f"Saldo BRL: {saldo_usdc_pos} BRL (Disponível) Pos venda")
            saldo_sei_pos = obter_saldo_crypt('ETH')
            print(f"Saldo ETH: {saldo_sei_pos} ETH (Disponível) Pos venda")
            
            criar_arquivo_saldo(saldo_sei,saldo_sei_pos,F'Vendi {valores_ganhos['total_quantidade_vendida']}','ETH')
            criar_arquivo_saldo(saldo_usdc,saldo_usdc_pos,f'Para receber {valores_ganhos['total_ganho']}','BRL')
            vendeu = vendeu +1
            if comprou != 0:
                comprou = comprou -1
            print(f' Na venda o comprou é: {comprou} e vendeu é: {vendeu}')
            return True
        except Exception as e:
            print(f"Erro ao realizar a ordem de venda: {e}")
            return False  # Após várias tentativas, falha na venda
        return False

def calcular_compra_venda(transacao):
    total_gasto = 0
    total_quantidade_comprada = 0
    total_ganho = 0
    total_quantidade_vendida = 0

    if transacao['side'] == 'BUY':
        # Se for uma compra
        for fill in transacao['fills']:
            total_gasto += float(fill['price']) * float(fill['qty'])
            total_quantidade_comprada += float(fill['qty'])
        preco_medio_compra = total_gasto / total_quantidade_comprada if total_quantidade_comprada > 0 else 0
        return {
            'tipo': 'compra',
            'total_gasto': total_gasto,
            'total_quantidade_comprada': total_quantidade_comprada,
            'preco_medio_compra': preco_medio_compra
        }

    elif transacao['side'] == 'SELL':
        # Se for uma venda
        for fill in transacao['fills']:
            total_ganho += float(fill['price']) * float(fill['qty'])
            total_quantidade_vendida += float(fill['qty'])
        preco_medio_venda = total_ganho / total_quantidade_vendida if total_quantidade_vendida > 0 else 0
        return {
            'tipo': 'venda',
            'total_ganho': total_ganho,
            'total_quantidade_vendida': total_quantidade_vendida,
            'preco_medio_venda': preco_medio_venda
        }

# Função para calcular lucro ou perda
def calcular_lucro_perda(compra, venda):
    preco_medio_compra = compra['preco_medio_compra']
    preco_medio_venda = venda['preco_medio_venda']
    taxa_percentual = 0.001
    total_quantidade_vendida = venda['total_quantidade_vendida']
     # Calcular o valor bruto de venda (antes da taxa)
    valor_bruto_venda = preco_medio_venda * total_quantidade_vendida
    
    # Calcular o valor líquido da venda (deduzindo a taxa)
    valor_liquido_venda = valor_bruto_venda * (1 - taxa_percentual)
    
    # Calcular o custo da compra (antes da taxa)
    custo_bruto_compra = preco_medio_compra * total_quantidade_vendida
    
    # Calcular o custo líquido da compra (deduzindo a taxa)
    custo_liquido_compra = custo_bruto_compra * (1 + taxa_percentual)
    
    # Calcular o lucro ou perda considerando a taxa
    lucro_perda = valor_liquido_venda - custo_liquido_compra
    
    # Escrever o resultado no arquivo
    adicionar_linha_ao_arquivo(f'Isso foi o lucro R${lucro_perda}')
    return lucro_perda

def toma_decisao(df):
    global rsi_anterior,preco_compra
    ultimo_precos = df.iloc[-1]  # Pega os últimos valores

    # Variáveis baseadas nos últimos preços
    rsi = ultimo_precos['rsi']
    bollinger_upper = ultimo_precos['bollinger_upper']
    bollinger_middle = ultimo_precos['bollinger_middle']
    bollinger_lower = ultimo_precos['bollinger_lower']
    close_price = ultimo_precos['close']
    macd_valor_atual  = ultimo_precos['macd_line']
    macd_signal_atual  = ultimo_precos['macd_signal']
    ema_9 = ultimo_precos['ema_9']
    ema_21 = ultimo_precos['ema_21']
    # macd_hist_atual  = ultimo_precos['MACD_hist']
    print(ultimo_precos)
    # 1. Condição de Compra
    # Comprar se o preço estiver abaixo da banda inferior de Bollinger e RSI < 30 and ema_9 > ema_21
    if close_price <= bollinger_middle and (rsi < 30 or 30 <= rsi <= 40)  and macd_valor_atual > macd_signal_atual:
        rsi_anterior = rsi
        print(f"Preço abaixo da banda inferior de Bollinger RSI entre 30 e 40. Considerar compra.")
        adicionar_linha_ao_arquivo(f"Preço abaixo da banda inferior de Bollinger RSI entre 45 e 60. Considerar compra.")
        return True
    elif rsi < 30 and close_price < bollinger_lower  and macd_valor_atual > macd_signal_atual: #
        print(f"RSI muito baixo e preço abaixo da banda inferior, MACD sugere reversão. Considerar compra.")
        adicionar_linha_ao_arquivo(f"RSI muito baixo, preço abaixo da banda inferior, MACD sugere reversão. Considerar compra.")
        return True
    elif close_price > bollinger_upper:
        print(f"Preço está acima da banda superior. Considerar esperar.")
        adicionar_linha_ao_arquivo(f"Preço está acima da banda superior. Evitar compra.")
        return 'Esperar'
        
    
    if rsi_anterior is not None:
        diferenca_rsi_compra = rsi_anterior - rsi #and macd_valor_atual > macd_signal_atual
        if diferenca_rsi_compra >= 5.5 and rsi < 35 and macd_valor_atual > macd_signal_atual :
            adicionar_linha_ao_arquivo(f"RSI caiu em {diferenca_rsi_compra}. Considerar compra.")
            print(f"RSI caiu em {diferenca_rsi_compra}. Considerar compra.")
            rsi_anterior = rsi  # Atualiza o valor do RSI anterior
            return True
    
    # if rsi < 30:
    #     adicionar_linha_ao_arquivo(f"RSI < 30 mas bollinger nao é maior que o close_price. Considerar venda.")
    #     rsi_anterior = rsi
    #     return True
    # 2. Condição de Venda
    # Vender se o preço estiver acima da banda superior de Bollinger e RSI > 70 and ema_9 < ema_21
    if close_price >= bollinger_middle and rsi >= 65 :
        rsi_anterior = rsi
        print(f"Preço acima da banda superior de Bollinger e RSI > 65. Considerar venda.")
        adicionar_linha_ao_arquivo(f"Preço acima da banda superior de Bollinger e RSI > 65. Considerar venda.")
        return False
    
    # if rsi > 75:
    #     rsi_anterior = rsi
    #     adicionar_linha_ao_arquivo(f"RSI > 75 mas bollinger nao é menor que o close_price. Considerar venda.")
    #     return False
    
    if rsi_anterior is not None:
        diferenca_rsi_venda = rsi - rsi_anterior
        if diferenca_rsi_venda >= 5.5 and rsi > 70:
            adicionar_linha_ao_arquivo(f"RSI subiu em {diferenca_rsi_compra}. Considerar vensa.")
            print(f"RSI subiu em {diferenca_rsi_venda}. Considerar venda.")
            rsi_anterior = rsi  # Atualiza o valor do RSI anterior
            return False
    
    rsi_anterior = rsi

def main_bot():
    global ultimo_valor,preco_compra,quantidade_comprada,preco_venda,ordem_compra,ordem_venda
    historico = obter_historico()
    indicadores = calcular_indicadores(historico)
    if ultimo_valor == 0:
        valor_inicial = pega_info_preco()[0]
        print(f"Preço Atual: {valor_inicial} INICIO")
        ultimo_valor = valor_inicial
        print('Pegando primeiro valor')
        saldo_usdc = obter_saldo_crypt('BRL')
        adicionar_linha_ao_arquivo(f'Valor de BRL inicial: {saldo_usdc}')
        print(f"Saldo BRL: {saldo_usdc} BRL (Disponível)")
        saldo_sei = obter_saldo_crypt('ETH')
        adicionar_linha_ao_arquivo(f'Valor de ETH inicial: {saldo_sei}')
        print(f"Saldo ETH: {saldo_sei} ETH (Disponível)")
    else:
        print('iniciando processo')
        valor_agora,step_size_symbol = pega_info_preco()
        print(f"Preço Atual: {valor_agora}")
        ultimo_precos = historico.iloc[-1]  # Pega os últimos valores
        
        # Variáveis baseadas nos últimos preços
        rsi = ultimo_precos['rsi']
        macd_atual = ultimo_precos['macd_line']
        macd_signal = ultimo_precos['macd_signal']
        print(f'RSI {rsi}, ultimo_valor é: {ultimo_valor} e valor_agora é: {valor_agora} e preco_compra é: {preco_compra} e preco venda é {preco_venda}')
        adicionar_linha_ao_arquivo(f'RSI {rsi}, ultimo_valor é: {ultimo_valor} e valor_agora é: {valor_agora} e preco_compra é: {preco_compra} e preco venda é {preco_venda}')
        decisao = toma_decisao(indicadores)
        percentual_stop_loss = 0.012
        stop_loss = float(preco_compra) - (float(preco_compra) * float(percentual_stop_loss))
        if float(valor_agora) <= stop_loss and preco_compra != 0.0 and macd_atual < macd_signal and rsi < 30:
            adicionar_linha_ao_arquivo(f'Preço caiu demais melhor vender agora, stop loss {stop_loss} valor agora{valor_agora}')
            # saldo_usdc = obter_saldo_crypt('BRL')
            # print(f"Saldo BRL: {saldo_usdc} BRL (Disponível)")
            # saldo_sei = obter_saldo_crypt('ETH')
            # print(f"Saldo ETH: {saldo_sei} ETH (Disponível)")
            # valor_venda = float(saldo_sei) * 0.4 # 40%
            # valor_venda =  ajustar_quantidade(valor_venda, step_size_symbol)
            # venda_final_loss = vender_mercado(crypt,valor_venda,valor_agora)
            # if venda_final_loss != False:
            #     preco_venda = valor_agora     
            # if venda_final_loss != False and ordem_compra != None and ordem_venda != None:
            #     lucro_perda = calcular_lucro_perda(ordem_compra, ordem_venda)
            # return
        # if rsi < 45 and float(ultimo_valor) > float(valor_agora) and (float(ultimo_valor) - float(valor_agora)) / float(ultimo_valor) > 0.0001 :
        # if decisao == True and float(ultimo_valor) > float(valor_agora) and preco_bom_para_compra :
        if decisao == True :
            saldo_usdc = obter_saldo_crypt('BRL')
            print(f"Saldo BRL: {saldo_usdc} BRL (Disponível)")
            saldo_sei = obter_saldo_crypt('ETH')
            print(f"Saldo ETH: {saldo_sei} ETH (Disponível)")
            
            valor_investido = float(saldo_usdc) * 0.6 # para comprar 30% 
            quantidade_compra = float(valor_investido) / float(valor_agora)
            quantidade_compra = ajustar_quantidade(quantidade_compra, step_size_symbol)
            valor_total_compra = float(quantidade_compra) * float(valor_agora)
            if valor_total_compra < 10.00:
                adicionar_linha_ao_arquivo(f'Preço menor do que R$10,00 {valor_total_compra}')
                # Calcula a quantidade mínima necessária para atingir R$10,00
                quantidade_minima = 10.00 / float(valor_agora)
                quantidade_compra = ajustar_quantidade(quantidade_minima, step_size_symbol)
                valor_total_compra_ajustado = quantidade_compra * float(valor_agora)
                while valor_total_compra_ajustado < 10.00:
                    # Incrementa a quantidade para atingir o valor mínimo
                    quantidade_compra += step_size_symbol
                    quantidade_compra = ajustar_quantidade(quantidade_compra, step_size_symbol)
                    valor_total_compra_ajustado = quantidade_compra * float(valor_agora)
                # Ajusta a quantidade mínima com base no step_size
                
                adicionar_linha_ao_arquivo(f'Ajuste para {quantidade_compra}')
            print(f"Comprando {quantidade_compra} {crypt}")
            comprar_final = comprar_mercado(crypt,quantidade_compra,valor_agora)
        
            adicionar_linha_ao_arquivo(f'Retorno compra final {comprar_final}')
            if comprar_final != False:
                # Armazenar o preço de compra e a quantidade comprada
                preco_compra = valor_agora
                ultimo_valor = valor_agora
                quantidade_comprada = quantidade_compra
            # else:
            #     adicionar_linha_ao_arquivo(f'Nao comprou pois variação {variacao_aceitavel_agora} e variação de compra {variacao_aceitavel_agora_compra} e deve comparar preço de compra {deve_comparar_preco_compra} ')

        # elif decisao == 'Compra':
        #     saldo_usdc = obter_saldo_crypt('BRL')
        #     print(f"Saldo BRL: {saldo_usdc} BRL (Disponível)")
        #     saldo_sei = obter_saldo_crypt('ETH')
        #     print(f"Saldo ETH: {saldo_sei} ETH (Disponível)")
        #     deve_comparar_preco_compra = float(preco_compra) > 0.0
        #     variacao_aceitavel_agora_compra = None
        #     variacao_percentual_compra = None
        #     limite_percentual = 0.1
        #     diferenca_preco_agora = float(valor_agora) - float(ultimo_valor)
            
        #     variacao_percentual_agora = (diferenca_preco_agora / float(ultimo_valor)) * 100
        #     variacao_aceitavel_agora = abs(variacao_percentual_agora) <= limite_percentual
        #     if preco_compra != 0.0: 
        #         diferenca_preco_compra = float(preco_compra) - float(ultimo_valor)
        #         variacao_percentual_compra = (diferenca_preco_compra / float(ultimo_valor)) * 100
        #         variacao_aceitavel_agora_compra = abs(variacao_percentual_compra) <= limite_percentual
            
        #     if variacao_aceitavel_agora_compra == None:
        #         variacao_aceitavel_agora_compra = float(valor_agora) <= float(preco_compra)
            
        #     if  (not deve_comparar_preco_compra and variacao_aceitavel_agora) or \
        #         (deve_comparar_preco_compra and variacao_aceitavel_agora_compra):
        #         # preco_compra = valor_agora
        #         valor_investido = float(saldo_usdc) * 0.4 # para comprar 30% 
        #         quantidade_compra = float(valor_investido) / float(valor_agora)
        #         quantidade_compra = ajustar_quantidade(quantidade_compra, step_size_symbol)
        #         valor_total_compra = quantidade_compra * float(valor_agora)
        #         if valor_total_compra < 10.00:
        #             # Calcula a quantidade mínima necessária para atingir R$10,00
        #             quantidade_minima = 10.00 / float(valor_agora)
        #             # Ajusta a quantidade mínima com base no step_size
        #             quantidade_compra = ajustar_quantidade(quantidade_minima, step_size_symbol)
        #         print(f"Comprando {quantidade_compra} {crypt}")
        #         comprar_final = comprar_mercado(crypt,quantidade_compra,valor_agora)
            
        #         if comprar_final != False:
        #             # Armazenar o preço de compra e a quantidade comprada
        #             preco_compra = valor_agora
        #             ultimo_valor = valor_agora
        #             quantidade_comprada = quantidade_compra
        # elif rsi > 59 and float(ultimo_valor) < float(valor_agora) and float(preco_compra) < float(valor_agora):
        elif decisao == False :
        # elif decisao == False and float(ultimo_valor) < float(valor_agora) and float(preco_compra) < float(valor_agora):
            saldo_sei = obter_saldo_crypt('ETH')
            print(f"Saldo ETH: {saldo_sei} ETH (Disponível)")
            saldo_usdc = obter_saldo_crypt('BRL')
            print(f"Saldo BRL: {saldo_usdc} BRL (Disponível)")
            
            margem_lucro = 0.0015
            #comissao = 0.001 #* (1.0 + comissao)
            preco_minimo_venda = float(preco_compra) * (1.0 + margem_lucro) 
            if float(valor_agora) >= float(preco_minimo_venda) :
                valor_venda = float(saldo_sei) * 0.4 # 30%
                
                valor_venda =  ajustar_quantidade(valor_venda, step_size_symbol)
                valor_min_venda = float(valor_venda) * float(valor_agora)
                adicionar_linha_ao_arquivo(f'Valor de tentativa é de {valor_venda}')
                if float(valor_min_venda) < 10.00 :
                    valor_venda = 10.00 / float(valor_agora)
                    # Ajusta a quantidade para corresponder ao step_size do par
                    valor_venda = ajustar_quantidade(valor_venda, step_size_symbol)
                    valor_venda = valor_venda + 0.0001
                    adicionar_linha_ao_arquivo(f'Novo Valor de tentativa é de {valor_venda}')
                    print(f'Valor de tentativa é de {valor_venda}')
                venda_final = vender_mercado(crypt,valor_venda,valor_agora)
                if venda_final != False:
                    preco_venda = valor_agora
                    
                if venda_final != False and ordem_compra != None and ordem_venda != None:
                    lucro_perda = calcular_lucro_perda(ordem_compra, ordem_venda)
            else:
                adicionar_linha_ao_arquivo(f"Preço de venda ({valor_agora}) ainda não atingiu a margem mínima de lucro ({preco_minimo_venda}), Não vendeu")    
        else:
            print('Não fiz nada')
        ultimo_valor = valor_agora
    
main_bot()

schedule.every(1).minutes.do(main_bot)

# Loop para manter o agendador rodando
while True:
    try:
        schedule.run_pending()
        time.sleep(1)
    except Exception as e:
        print(f"Ocorreu um erro: {e}")
        print("Reiniciando programa em 5 segundos...")
        time.sleep(5)
