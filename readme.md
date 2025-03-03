Estratégia de Compra e Venda no Trading Bot
1️⃣ Condições de Compra
Objetivo:
Comprar quando o ativo estiver próximo do fundo, com sinais claros de reversão para cima e confirmação de momentum positivo.

Condições:

Evitar compras no topo:
O preço deve estar abaixo da banda superior de Bollinger:

python
last['close'] < last['BBU_20_2.0']
Proximidade das EMAs de suporte:
O preço deve estar próximo das médias móveis exponenciais (EMA_9 e EMA_21):

python
last['close'] * 1.009 > last['EMA_9']
last['close'] * 1.009 > last['EMA_21']
Confirmação de momentum positivo:
O histograma do MACD deve ser maior que 0.6, indicando força na tendência:

python
last['MACDh_12_26_9'] > 0.6
Tendência forte identificada pelo ADX:
O índice direcional médio (ADX) deve ser maior que 19:

python
last['ADX'] > 19
Confirmação pelo oscilador estocástico (KDJ):
A linha K deve estar acima da linha D, com uma diferença mínima de 4 pontos, e a linha J deve estar abaixo de 100:

python
last['K_14_3'] > last['D_14_3']
last['K_14_3'] - last['D_14_3'] >= 4
last['J_14_3'] < 100
PSAR indicando tendência de alta:
O preço deve estar acima do valor do indicador PSAR:

python
last['PSAR'] < last['close']
Novas condições baseadas em dados anteriores:

O preço atual deve ser maior que o preço anterior:

python
last['close'] > previous['close']
O valor do MACD atual deve ser maior que o anterior, indicando crescimento:

python
last['MACD_12_26_9'] > previous['MACD_12_26_9']
A linha K do oscilador estocástico deve estar subindo em relação ao dado anterior:

python
last['K_14_3'] > previous['K_14_3']
2️⃣ Condições de Venda
Objetivo:
Vender quando o ativo estiver próximo do topo, com sinais claros de reversão para baixo e perda de força na tendência.

Condições:

Atingiu o topo:
O preço deve estar acima da banda superior de Bollinger:

python
last['close'] > last['BBU_20_2.0']
Confirmação da reversão pelo MACD e PSAR:

O histograma do MACD deve ser negativo, e o preço deve estar abaixo do valor do PSAR:

python
last['MACDh_12_26_9'] < 0 and last['close'] < last['PSAR']
Padrão bearish identificado com ADX fraco:

Se o ADX for menor que 27, o padrão bearish é confirmado pelo preço abaixo da EMA_9 e PSAR:

python
sell_candle_condition and last['ADX'] < 27 and last['close'] < last['EMA_9'] and last['close'] < last['PSAR']
Oscilador estocástico indicando reversão:

A linha K deve cruzar para baixo da linha D, enquanto o MACD está abaixo da sua linha de sinal e o preço está abaixo do PSAR:

python
last['K_14_3'] < last['D_14_3'] and 
last['MACD_12_26_9'] < last['MACDs_12_26_9'] and 
last['close'] < last['PSAR']
Confirmação adicional com ADX forte:

Se o ADX for maior que 27, a venda é confirmada pela queda no MACD e no PSAR:

python
(last['ADX'] > 27 and 
 last['MACD_12_26_9'] < last['MACDs_12_26_9'] and 
 last['close'] < last['PSAR'])
📌 Observações Importantes
Renomear a biblioteca numpy:
Para evitar erros no arquivo squeeze_pro, é necessário renomear a biblioteca numpy no código. Substitua todas as ocorrências de NaN por nan.

Configurar o ambiente virtual Python:
É fundamental utilizar um ambiente virtual para gerenciar as dependências do projeto. Siga os passos abaixo:

Alem de criar suas varaiveis de ambiente em um arquivo .env

Crie um ambiente virtual:

bash
python -m venv venv
Ative o ambiente virtual:

No Windows:

bash
venv\Scripts\activate
No Linux/Mac:

bash
source venv/bin/activate
Instale as dependências listadas no arquivo requirements.txt:

bash
pip install -r requirements.txt
Seguindo essas orientações, você terá uma estratégia robusta para compra e venda automatizada no seu trading bot! 🚀