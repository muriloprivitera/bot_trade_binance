Estratégia de Compra e Venda no Trading Bot
1️⃣ Condições de Compra
Objetivo:
Comprar quando o ativo estiver próximo do fundo, com sinais de reversão para cima.

Condições:
Preço próximo da banda inferior de Bollinger

last['close'] <= last['BBL_20_2.0'] * 1.015
Indica que o ativo pode estar em uma zona de sobrevenda.
RSI abaixo de 49

last['RSI_14'] < 49
Sinaliza que o ativo pode estar sobrevendido, aumentando a chance de reversão.
Preço próximo da EMA_9, podendo estar levemente abaixo

last['close'] >= last['EMA_9'] * 0.997
Permite que o preço esteja um pouco abaixo da EMA_9, sem exigir que tenha cruzado para cima.
MACD indicando reversão para cima

last['MACD_12_26_9'] >= last['MACDs_12_26_9'] * 1.04
O MACD precisa estar acima da sua linha de sinal, indicando uma possível mudança de tendência.
MACD não pode estar muito negativo

last['MACD_12_26_9'] >= -35
Evita compras quando a queda ainda está muito forte.
2️⃣ Condições de Venda
Objetivo:
Vender quando o ativo estiver próximo do topo, com sinais de reversão para baixo.

Condições:
Preço próximo da banda superior de Bollinger

last['close'] >= last['BBU_20_2.0'] * 0.99
Indica que o ativo pode estar em uma zona de sobrecompra.
RSI acima de 50

last['RSI_14'] >= 50
Sinaliza que o ativo pode estar sobrecomprado e começando a perder força.
Preço um pouco abaixo da EMA_9

last['close'] <= last['EMA_9'] * 0.999
Indica que a alta pode estar perdendo força e o preço pode cair em breve.
MACD indicando reversão para baixo

last['MACD_12_26_9'] <= last['MACDs_12_26_9'] * 1.05
O MACD precisa estar abaixo da linha de sinal, sugerindo uma possível queda.
📊 Resumo Rápido
Indicador	Compra	Venda
Bandas de Bollinger	Preço próximo da banda inferior	Preço próximo da banda superior
RSI	Menor que 49 (sobrevenda)	Maior que 50 (sobrecompra)
EMA_9	Preço >= EMA_9 * 0.997	Preço <= EMA_9 * 0.999
MACD	Acima da linha de sinal e não muito negativo	Abaixo da linha de sinal