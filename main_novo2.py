from binance.client import Client
import pandas as pd
import numpy as np
import pandas_ta as ta
import time
import schedule
# import logging
import os
import requests
from dotenv import load_dotenv
import math  # Importado para cálculo correto de múltiplos

# Configurações iniciais
load_dotenv()

# Configuração de logs
# logging.basicConfig(
#     level=logging.INFO,
#     format='%(asctime)s - %(levelname)s - %(message)s',
#     handlers=[
#         logging.FileHandler('logs/trading.log'),
#         logging.StreamHandler()
#     ]
# )
# Configuração do Telegram
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
BINANCE_API_KEY = os.getenv('BINANCE_API_KEY')
BINANCE_API_SECRET = os.getenv('BINANCE_API_SECRET')
BINANCE_API_KEY_TEST = os.getenv('BINANCE_API_KEY_TEST')
BINANCE_API_SECRET_TEST = os.getenv('BINANCE_API_SECRET_TEST')
# Parâmetros do robô
SYMBOL = 'SOLBRL'
INTERVAL = '15m'  # Intervalo otimizado para reduzir ruído
STOP_LOSS = 0.03  # 1.3%
TAKE_PROFIT = 0.005  # 0,5%
MAX_POSITION = 0.3  # 30% do saldo por operação
MAX_POSITION_SELL = 1  # 30% do saldo por operação
FEE = 0.001  # Taxa da Binance

# Inicialização da API
# client = Client('', '',testnet=True)
client = Client(BINANCE_API_KEY, BINANCE_API_SECRET)

class TradingBot:
    def __init__(self):
        self.position = None
        self.entry_price = 0.0
        self.entry_qty = 0.0
        self.balance_log = {
            'initial_brl': 0.0,
            'initial_sol': 0.0,
            'current_brl': 0.0,
            'current_sol': 0.0
        }
        
        # Criar pastas necessárias
        os.makedirs('logs', exist_ok=True)
        os.makedirs('registros_saldo', exist_ok=True)

    def send_telegram_message(self,message):
        """Envia uma mensagem para o Telegram."""
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
        response = requests.post(url, data=data)
        
    def get_historical_data(self, interval=INTERVAL, limit=500):
        """Obtém dados históricos formatados"""
        klines = client.get_klines(
            symbol=SYMBOL,
            interval=interval,
            limit=limit
        )
        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base',
            'taker_quote_vol', 'ignore'
        ]).astype({
            'open': float, 'high': float, 'low': float,
            'close': float, 'volume': float
        })
        return df

    def calculate_indicators(self, df):
        """Calcula todos os indicadores técnicos usando pandas-ta"""
        # Indicadores básicos
        df.ta.rsi(length=14, append=True)
        df.ta.ema(length=9, append=True)
        df.ta.ema(length=21, append=True)
        df.ta.ema(length=50, append=True)
       
        
        # Bollinger Bands
        df.ta.bbands(length=20, std=2, append=True)
        
        # MACD
        df.ta.macd(fast=12, slow=26, signal=9, append=True)
        
        # ATR para volatilidade
        df.ta.atr(length=14, append=True)
        df.ta.kdj(length=14, append=True)
        
        df['candle_color'] = df.apply(
            lambda df: 'green' if df['close'] > df['open'] 
                        else ('red' if df['close'] < df['open'] else 'doji'),
            axis=1
        )
        df['ADX'] = ta.adx(df['high'], df['low'], df['close'])['ADX_14']
         # Calcular Parabolic SAR
        psar = ta.psar(high=df['high'], low=df['low'], close=df['close'], af0=0.02, af=0.02, max_af=0.2)
        if psar is not None and not psar.empty:
            # Criar uma única coluna consolidada para o PSAR
            df['PSAR'] = np.where(psar['PSARl_0.02_0.2'].notna(), psar['PSARl_0.02_0.2'], psar['PSARs_0.02_0.2'])

            # Remover linhas com NaN para evitar erros
            df.dropna(subset=['PSAR'], inplace=True)
        return df.dropna()

    def get_balance(self, asset):
        """Obtém saldo formatado"""
        valor = float(client.get_asset_balance(asset,recvWindow=60000)['free'])
        return f"{valor:.10f}"

    # def log_transaction(self, side, detalhes):
    #     """
    #     Implementa o log da transação.
    #     Você pode modificar para salvar em banco de dados, enviar para um arquivo log, etc.
    #     """
    #     logging.info(f"Transação {side}: {detalhes}")

    def execute_order(self, side, quantity, price, order_type="LIMIT"):
        try:
            attempt = 15  # Número máximo de tentativas
            current_attempt = 0  # Contador de tentativas

            # Obter informações do par
            symbol_info = client.get_symbol_info(SYMBOL)

            # Obter step size, minQty e minNotional
            step_size = float([f['stepSize'] for f in symbol_info['filters'] if f['filterType'] == 'LOT_SIZE'][0])
            min_qty = float([f['minQty'] for f in symbol_info['filters'] if f['filterType'] == 'LOT_SIZE'][0])
            min_notional = float([f['minNotional'] for f in symbol_info['filters'] if f['filterType'] == 'NOTIONAL'][0])

            # Obter saldo da conta
            account_info = client.get_account(recvWindow=60000)
            balances = {asset['asset']: float(asset['free']) for asset in account_info['balances']}

            # Ajustar a quantidade para o step size correto
            adjusted_qty = round(quantity - (quantity % step_size), 8)

            # Calcular o valor total da ordem (em BRL)
            total_value = adjusted_qty * price

            # **1️⃣ Ajustar quantidade mínima para compra (BUY)**
            if side == "BUY":
                available_balance = balances.get("BRL", 0)  # Saldo disponível em BRL
                max_qty = available_balance / price  # Quantidade máxima de SOL que pode ser comprada
                adjusted_qty = min(adjusted_qty, max_qty)  # Garante que a quantidade não ultrapasse o saldo
                total_cost = adjusted_qty * price  # Custo total da compra
                if total_cost > available_balance:
                    self.send_telegram_message(f"Saldo insuficiente para compra! Tentando gastar {total_cost:.2f} BRL, mas disponível apenas {available_balance:.2f} BRL")
                    # logging.error(f"Saldo insuficiente para compra! Tentando gastar {total_cost:.2f} BRL, mas disponível apenas {available_balance:.2f} BRL")
                    return None  # Cancela a ordem

            # **2️⃣ Ajustar quantidade mínima para venda (SELL)**
            elif side == "SELL":
                available_balance = balances.get("SOL", 0)  # Saldo disponível em SOL
                adjusted_qty = min(adjusted_qty, available_balance)  # Garante que a quantidade não ultrapasse o saldo
                if adjusted_qty > available_balance:
                    self.send_telegram_message(f"Saldo insuficiente para venda! Tentando vender {quantity:.6f} SOL, mas disponível apenas {available_balance:.6f} SOL")
                    # logging.error(f"Saldo insuficiente para venda! Tentando vender {quantity:.6f} SOL, mas disponível apenas {available_balance:.6f} SOL")
                    return None  # Cancela a ordem

            # **3️⃣ Se o valor total da ordem for menor que minNotional, ajustar a quantidade corretamente**
            if total_value < min_notional:
                # Calcular a quantidade necessária para atingir minNotional
                min_qty_required = min_notional / price
                # Arredondar para o próximo múltiplo válido de step_size
                adjusted_qty = math.ceil(min_qty_required / step_size) * step_size
                # logging.warning(f"Ajustando quantidade para atender minNotional {min_notional} BRL: {adjusted_qty} SOL")
                self.send_telegram_message(f"Ajustando quantidade para atender minNotional {min_notional} BRL: {adjusted_qty} SOL")

            # Garantir que a quantidade seja maior que minQty
            if adjusted_qty < min_qty:
                adjusted_qty = min_qty
                # logging.warning(f"Ajustando quantidade para o mínimo permitido {min_qty} SOL")
                self.send_telegram_message(f"Ajustando quantidade para o mínimo permitido {min_qty} SOL")

            # Verificação final: garantir que o valor total da ordem atenda `minNotional`
            if adjusted_qty * price < min_notional:
                # logging.error(f"Erro: Valor total da ordem ({adjusted_qty * price} BRL) ainda está abaixo de {min_notional} BRL")
                self.send_telegram_message(f"Erro: Valor total da ordem ({adjusted_qty * price} BRL) ainda está abaixo de {min_notional} BRL")
                return None

            while current_attempt < attempt:
                # Criar ordem de mercado ou limitada conforme configuração
                if order_type == "MARKET":
                    order = client.create_order(
                        symbol=SYMBOL,
                        side=side,
                        type=Client.ORDER_TYPE_MARKET,
                        quantity=adjusted_qty,recvWindow=60000
                    )
                else:  # Default: LIMIT
                    order = client.create_order(
                        symbol=SYMBOL,
                        side=side,
                        type=Client.ORDER_TYPE_LIMIT,
                        timeInForce=Client.TIME_IN_FORCE_GTC,
                        quantity=adjusted_qty,
                        price=round(price, 2),recvWindow=60000
                    )

                # logging.info(f"Ordem enviada (tentativa {current_attempt + 1}/{attempt}): {order}")

                time.sleep(4)  # Espera 4 segundos para ver se a ordem executa

                # Verificar status da ordem
                order_status = client.get_order(symbol=SYMBOL, orderId=order['orderId'],recvWindow=60000)
                executed_qty = float(order_status.get('executedQty', 0))

                if executed_qty > 0:
                    # logging.info(f"Ordem {side} executada com sucesso: {executed_qty} {SYMBOL}")
                    self.send_telegram_message(f"Ordem {side} executada com sucesso: {executed_qty} {SYMBOL}")
                    return order
                else:
                    # logging.warning(f"Ordem {side} não executada, tentando novamente...")
                    # self.send_telegram_message(f"Ordem {side} não executada, tentando novamente...")

                    # Se a ordem não foi executada, cancelar antes de tentar de novo
                    # logging.info(f"Cancelando ordem não executada: {order['orderId']}")
                    self.send_telegram_message(f"Cancelando ordem não executada: {order['orderId']}")
                    client.cancel_order(symbol=SYMBOL, orderId=order['orderId'],recvWindow=60000)

                    current_attempt += 1
            # client.cancel_order(symbol=SYMBOL, orderId=order['orderId'],recvWindow=60000)
            # logging.error(f"Ordem {side} falhou após {attempt} tentativas")
            self.send_telegram_message(f"Ordem {side} falhou após {attempt} tentativas")
            return None

        except Exception as e:
            # logging.error(f"Erro na ordem {side}: {str(e)}")
            self.send_telegram_message(f"Erro na ordem {side}: {str(e)}")
            return None

    def identify_candle_pattern(self,candle):
        """
        Recebe um dicionário 'candle' com as chaves: 'open', 'high', 'low', 'close'
        e retorna uma lista com os padrões candlestick identificados.
        
        Padrões identificados:
        - Bullish Marubozu: candle de alta com pouca sombra, onde open ~ low e close ~ high.
        - Bearish Marubozu: candle de baixa com pouca sombra, onde open ~ high e close ~ low.
        - Hammer: candle bullish com corpo pequeno e sombra inferior longa (pelo menos 2x o corpo), pouca ou nenhuma sombra superior.
        - Shooting Star: candle bearish com corpo pequeno e sombra superior longa (pelo menos 2x o corpo), pouca ou nenhuma sombra inferior.
        - Dragonfly Doji: candle em que open, close e high são quase iguais, com uma longa sombra inferior.
        - Gravestone Doji: candle em que open, close e low são quase iguais, com uma longa sombra superior.

        Os parâmetros de tolerância podem ser ajustados conforme a volatilidade do ativo.
        """
        o = candle['open']
        h = candle['high']
        l = candle['low']
        c = candle['close']

        # Determina a "cor" do candle: verde para alta, vermelho para baixa e doji para neutro.
        if c > o:
            candle_color = "green"
        elif c < o:
            candle_color = "red"
        else:
            candle_color = "doji"

        # Calcula o corpo e as sombras
        body = abs(c - o)
        upper_shadow = h - max(o, c)
        lower_shadow = min(o, c) - l

        # Define uma tolerância baseada na amplitude do candle; ajuste conforme necessário
        tol = 0.001 * (h - l)  # 0,1% da amplitude total

        patterns = []

        # Bullish Marubozu: candle de alta sem sombras significativas
        if candle_color == "green" and abs(o - l) < tol and abs(h - c) < tol:
            patterns.append("Bullish Marubozu")

        # Bearish Marubozu: candle de baixa sem sombras significativas
        if candle_color == "red" and abs(o - h) < tol and abs(c - l) < tol:
            patterns.append("Bearish Marubozu")

        # Hammer (Martelo): candle bullish com corpo pequeno e sombra inferior longa
        if candle_color == "green" and lower_shadow > 2 * body and upper_shadow < body:
            patterns.append("Hammer")

        # Shooting Star (Estrela Cadente): candle bearish com corpo pequeno e sombra superior longa
        if candle_color == "red" and upper_shadow > 2 * body and lower_shadow < body:
            patterns.append("Shooting Star")

        # Dragonfly Doji: candle com open, close e high muito próximos e sombra inferior longa
        if candle_color == "doji" and abs(o - h) < tol and lower_shadow > 2 * body:
            patterns.append("Dragonfly Doji")

        # Gravestone Doji: candle com open, close e low muito próximos e sombra superior longa
        if candle_color == "doji" and abs(o - l) < tol and upper_shadow > 2 * body:
            patterns.append("Gravestone Doji")

        if not patterns:
            patterns.append("No pattern")

        return patterns

    def check_risk_management(self, current_price):
        """Verifica stop loss e take profit"""
        if self.position == 'LONG':
            pl_percent = (current_price - self.entry_price) / self.entry_price
            
            if pl_percent <= -STOP_LOSS:
                # logging.warning(f"Stop loss acionado! Perda: {pl_percent*100:.2f}%")
                self.send_telegram_message(f"Stop loss acionado! Perda: {pl_percent*100:.2f}%")
                return 'SELL'
                
            if pl_percent >= TAKE_PROFIT:
                # logging.info(f"Take profit alcançado! Ganho: {pl_percent*100:.2f}%")
                self.send_telegram_message(f"Take profit alcançado! 🎯 Ganho: {pl_percent*100:.2f}%")
                return 'SELL'
        
        return 'HOLD'

    def trading_strategy(self, df):
        """Implementa a lógica de decisão"""
        last = df.iloc[-1]
        # logging.info(f"Indicadores: \n{last}" )
        # return
        previous = df.iloc[-2]
        candle_patterns = self.identify_candle_pattern(last)

        # Para compra, você pode querer padrões bullish como Hammer ou Bullish Marubozu:
        buy_candle_condition = any(pat in candle_patterns for pat in ['Hammer', 'Bullish Marubozu', 'Dragonfly Doji','Inverted Hammer'])

        # Para venda, você pode querer padrões bearish como Shooting Star ou Bearish Marubozu:
        sell_candle_condition = any(pat in candle_patterns for pat in ['Shooting Star', 'Bearish Marubozu', 'Gravestone Doji'])
        
        buy_conditions = [
            last['close'] < last['BBU_20_2.0'], # Não comprar no topo
            # (last['BBU_20_2.0'] - last['close']) / last['BBU_20_2.0'] > 0.003,
            last['close'] * 1.009 > last['EMA_9'], # Próximo das EMAs de suporte
            last['close'] * 1.009 > last['EMA_21'],
            last['MACDh_12_26_9'] > 0.6, # Confirmação do momentum positivo
            last['ADX'] > 19, # Tendência forte
            last['K_14_3'] > last['D_14_3'],
            last['K_14_3'] - last['D_14_3'] >= 4,
            last['J_14_3'] < 100,
            # last['PSARl_0.02_0.2'] > 0,  # Verifica se existe um valor PSAR para tendência de alta
            last['PSAR'] < last['close'],  # PSAR está abaixo do preço
            # Novas Condições Baseadas no Dado Anterior
            last['close'] > previous['close'],  # Preço atual maior que o anterior
            last['MACD_12_26_9'] > previous['MACD_12_26_9'],  # MACD está subindo
            # last['ADX'] > previous['ADX'],  # ADX aumentando (tendência ganhando força)
            last['K_14_3'] > previous['K_14_3'],  # KDJ subindo
            
        ]
        
        sell_conditions = [
            last['close'] > last['BBU_20_2.0'], #Atingiu o topo
            last['MACDh_12_26_9'] < 0 and last['close'] < last['PSAR'], #sempre vai ser menor redundancia
            sell_candle_condition and last['ADX'] < 27 and last['close'] < last['EMA_9'] and last['close'] < last['PSAR'],                  # Padrão de candle bearish identificado
            last['K_14_3'] < last['D_14_3'] and last['MACD_12_26_9'] < last['MACDs_12_26_9'] and last['close'] < last['PSAR'],                  # Padrão de candle bearish identificado
            (last['ADX'] > 27 and last['MACD_12_26_9'] < last['MACDs_12_26_9'] and last['close'] < last['PSAR'])
        ]
        # logging.info(f">>>>>>> Compra {buy_conditions} com candle: {candle_patterns}" )
        # logging.info(f">>>>>>> Venda {sell_conditions} com candle: {candle_patterns}")
        if all(buy_conditions):
            self.send_telegram_message(f"Indicadores na compra \n{last}")
            return 'BUY'
        elif any(sell_conditions) and last['close'] >= self.entry_price :
            self.send_telegram_message(f"Indicadores na venda \n{last}")
            return 'SELL'
        self.send_telegram_message(f"TESTE")
        return 'HOLD'

    def ajustar_quantidade(self,quantity, step_size):
        precision = len(str(step_size).split('.')[1])
        return round(float(quantity) // float(step_size) * float(step_size), precision)
    
    def processar_detalhes_ordem(self,order):
        """
        Processa os detalhes dos fills de uma ordem.
        Retorna:
        - preco_medio: média ponderada dos preços de execução
        - quantidade_total: soma das quantidades executadas
        - comissoes: dicionário com a soma das comissões por ativo
        """
        fills = order.get('fills', [])
        if not fills:
            print("Sem fills na ordem!")
            return None, None, None

        quantidade_total = 0.0
        soma_ponderada = 0.0
        comissoes = {}

        for fill in fills:
            try:
                qty = float(fill.get('qty', 0))
                preco = float(fill.get('price', 0))
                comissao = float(fill.get('commission', 0))
                ativo_comissao = fill.get('commissionAsset', '')
            except Exception as e:
                print(f"Erro ao converter valores do fill: {e}")
                continue

            # Acumula quantidade e soma ponderada do preço
            quantidade_total += qty
            soma_ponderada += preco * qty

            # Agrupa comissões por ativo
            if ativo_comissao in comissoes:
                comissoes[ativo_comissao] += comissao
            else:
                comissoes[ativo_comissao] = comissao

        preco_medio = soma_ponderada / quantidade_total if quantidade_total != 0 else 0
        return preco_medio, quantidade_total, comissoes
    
    def converter_comissao_para_brl(self,comissoes, taxa_conversao):
        """
        Converte as comissões para BRL utilizando um dicionário com as taxas de conversão.

        text
        Parâmetros:
        comissoes: dicionário no formato {'BNB': valor, ...}
        taxa_conversao: dicionário com taxa de conversão, ex: {'BNB': 150.0}

        Retorna:
        comissoes_brl: dicionário com as comissões convertidas para BRL.
        """
        comissoes_brl = {}
        for ativo, valor in comissoes.items():
            if ativo in taxa_conversao:
                comissoes_brl[ativo] = valor * taxa_conversao[ativo]
            else:
                # Se não houver taxa definida, você pode optar por manter o valor original ou definir como None
                comissoes_brl[ativo] = valor  
        return comissoes_brl
    
    def obter_taxa_brl_para(self,ativo):
        """
        Função fictícia para obter a taxa de conversão do ativo para BRL.
        Substitua essa função pela implementação que recupere a taxa real.

        text
        Exemplo: 1 BNB = 150 BRL.
        """
        data = client.get_symbol_ticker(symbol=ativo)
        price = float(data["price"])
        taxas = {'BNB': price}
        return taxas.get(ativo, 1)
    
    def run(self):
        """Executa o ciclo completo de trading"""
        try:
            
            # Obter e processar dados
            df = self.get_historical_data()
            df = self.calculate_indicators(df)
            
            # Verificar gerenciamento de risco
            current_price = df.iloc[-1]['close']
            risk_action = self.check_risk_management(current_price)
            
            # Tomar decisão estratégica
            strategy_action = self.trading_strategy(df)
            # logging.info("Risk Action "+ risk_action)
            # logging.info("Estrategia "+ strategy_action)
            
            if  (self.position == 'LONG' or self.position == 'LONG2') and (risk_action == 'SELL' or strategy_action == 'SELL'):
                sol_balance = self.balance_log['current_sol']
                if sol_balance > 0.0001:  # Apenas vende se houver saldo suficiente
                    qty = sol_balance * MAX_POSITION_SELL  # Vende apenas uma parte do saldo
                    self.balance_log = {
                        'initial_brl': self.get_balance('BRL'),
                        'initial_sol': self.get_balance('SOL'),
                    }
                    self.send_telegram_message(f"Valores Iniciais {self.balance_log}")
                    order = self.execute_order('SELL', qty, current_price)
                    # logging.info(f"Ordem {order}")
                    self.send_telegram_message(f" Ordem : {order}")

                    if order:
                        # Processa os detalhes dos fills da ordem
                        preco_medio, qtd_exec, comissoes = self.processar_detalhes_ordem(order)
                        # Obtem taxa de conversão para cada ativo nas comissões,
                        # por enquanto, usando apenas BNB como exemplo.
                        taxa_conversao = {'BNB': self.obter_taxa_brl_para('BNB')}
                        comissoes_brl = self.converter_comissao_para_brl(comissoes, taxa_conversao)
                        # Log da transação com os dados processados
                        # self.log_transaction('SELL', {
                        #     'price': preco_medio,          # Preço médio de execução
                        #     'quantity': qtd_exec,          # Quantidade total executada
                        #     'commission': comissoes,       # Comissões por ativo
                        #     'commission_brl': comissoes_brl, # Comissões convertidas para BRL
                        #     'sell_price' : preco_medio * qtd_exec
                        #     'reason': 'Risk/Strategy Sell Signal'
                        # })
                        infos = {
                            'price': preco_medio,          # Preço médio de execução
                            'quantity': qtd_exec,          # Quantidade total executada
                            'commission': comissoes,       # Comissões por ativo
                            'commission_brl': comissoes_brl, # Comissões convertidas para BRL
                            'sell_price' : preco_medio * qtd_exec,
                            'reason': 'Risk/Strategy Sell Signal'
                        }
                        self.send_telegram_message(f"📉 Venda : {infos}")
                        # logging.info(f"Valor estimado em BRL da venda: {brl_received:.2f} BRL")
                        self.position = None  # Se quiser manter a posição parcial, pode remover essa linha
                        self.balance_log = {
                            'current_brl': self.get_balance('BRL'),
                            'current_sol': self.get_balance('SOL')
                        }
                        self.send_telegram_message(f"Valores finais {self.balance_log}")

            elif strategy_action == 'BUY' and not self.position:
            # elif strategy_action == 'BUY':
                brl_balance = self.balance_log['current_brl']
                if brl_balance > 10:
                    raw_qty = (brl_balance * MAX_POSITION) / current_price
                    #  Verificação de saldo para evitar erro de saldo insuficiente
                    
                    # logging.info(f"Quantidade {raw_qty} SOL que será comprada com {brl_balance} BRL")
                    self.balance_log = {
                        'initial_brl': self.get_balance('BRL'),
                        'initial_sol': self.get_balance('SOL'),
                    }
                    self.send_telegram_message(f"Valores Iniciais {self.balance_log}")
                    order = self.execute_order('BUY', raw_qty, current_price)
                    if order:
                        preco_medio, qtd_exec, comissoes = self.processar_detalhes_ordem(order)
                        taxa_conversao = {'BNB': self.obter_taxa_brl_para('BNB')}
                        comissoes_brl = self.converter_comissao_para_brl(comissoes, taxa_conversao)
                        # self.log_transaction('BUY', {
                        #     'price': preco_medio,           # Preço médio real de execução
                        #     'quantity': qtd_exec,           # Quantidade total executada
                        #     'commission': comissoes,        # Comissões agrupadas por ativo
                        #     'commission_brl': comissoes_brl,  # Comissões convertidas para BRL
                        #     'reason': 'Strategy Buy Signal'
                        # })
                        infos = {
                            'price': preco_medio,           # Preço médio real de execução
                            'quantity': qtd_exec,           # Quantidade total executada
                            'commission': comissoes,        # Comissões agrupadas por ativo
                            'commission_brl': comissoes_brl,  # Comissões convertidas para BRL
                            'reason': 'Strategy Buy Signal',
                            'buy_price':preco_medio * qtd_exec
                        }
                        self.position = 'LONG'
                        self.entry_price = current_price
                        self.entry_qty = raw_qty
                        self.send_telegram_message(f"📈 Compra : {infos}")
                        self.balance_log = {
                            'current_brl': self.get_balance('BRL'),
                            'current_sol': self.get_balance('SOL')
                        }
                        self.send_telegram_message(f"Valores finais {self.balance_log}")
            # logging.info("Ciclo completo executado com sucesso")
            
            
        except Exception as e:
            # logging.error(f"Erro no ciclo principal: {str(e)}")
            self.send_telegram_message(f"Erro no ciclo principal: {str(e)}")

if __name__ == "__main__":
    bot = TradingBot()
    bot.run()
    # Agendador para rodar a cada 15 minutos
    schedule.every(14).minutes.do(bot.run)
    
    # logging.info("Iniciando robô de trading...")
    bot.send_telegram_message(f"Iniciando robô de trading...")
    while True:
        try:
            schedule.run_pending()
            time.sleep(1)
        except KeyboardInterrupt:
            # logging.info("Interrupção do usuário, encerrando...")
            bot.send_telegram_message(f"Interrupção do usuário, encerrando...")
            break
        except Exception as e:
            # logging.error(f"Erro no agendador: {str(e)}")
            bot.send_telegram_message(f"Erro no agendador: {str(e)}")
            time.sleep(60)