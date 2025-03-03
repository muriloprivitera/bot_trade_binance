# EstratÃ©gia de Compra e Venda no Trading Bot

## **1ï¸â£ CondiÃ§Ãµes de Compra**

### **Objetivo:**
Comprar quando o ativo estiver prÃ³ximo do fundo, com sinais de reversÃ£o para cima.

### **CondiÃ§Ãµes:**

1. **PreÃ§o prÃ³ximo da banda inferior de Bollinger**
   - `last['close'] <= last['BBL_20_2.0'] * 1.015`
   - Indica que o ativo pode estar em uma zona de sobrevenda.

2. **RSI abaixo de 49**
   - `last['RSI_14'] < 49`
   - Sinaliza que o ativo pode estar sobrevendido, aumentando a chance de reversÃ£o.

3. **PreÃ§o prÃ³ximo da EMA_9, podendo estar levemente abaixo**
   - `last['close'] >= last['EMA_9'] * 0.997`
   - Permite que o preÃ§o esteja um pouco abaixo da EMA_9, sem exigir que tenha cruzado para cima.

4. **MACD indicando reversÃ£o para cima**
   - `last['MACD_12_26_9'] >= last['MACDs_12_26_9'] * 1.04`
   - O MACD precisa estar acima da sua linha de sinal, indicando uma possÃ­vel mudanÃ§a de tendÃªncia.

5. **MACD nÃ£o pode estar muito negativo**
   - `last['MACD_12_26_9'] >= -35`
   - Evita compras quando a queda ainda estÃ¡ muito forte.

---

## **2ï¸â£ CondiÃ§Ãµes de Venda**

### **Objetivo:**
Vender quando o ativo estiver prÃ³ximo do topo, com sinais de reversÃ£o para baixo.

### **CondiÃ§Ãµes:**

1. **PreÃ§o prÃ³ximo da banda superior de Bollinger**
   - `last['close'] >= last['BBU_20_2.0'] * 0.99`
   - Indica que o ativo pode estar em uma zona de sobrecompra.

2. **RSI acima de 50**
   - `last['RSI_14'] >= 50`
   - Sinaliza que o ativo pode estar sobrecomprado e comeÃ§ando a perder forÃ§a.

3. **PreÃ§o um pouco abaixo da EMA_9**
   - `last['close'] <= last['EMA_9'] * 0.999`
   - Indica que a alta pode estar perdendo forÃ§a e o preÃ§o pode cair em breve.

4. **MACD indicando reversÃ£o para baixo**
   - `last['MACD_12_26_9'] <= last['MACDs_12_26_9'] * 1.05`
   - O MACD precisa estar abaixo da linha de sinal, sugerindo uma possÃ­vel queda.

---

## **ð Resumo RÃ¡pido**

| **Indicador**  | **Compra**  | **Venda**  |
|---------------|------------|------------|
| **Bandas de Bollinger** | PreÃ§o prÃ³ximo da banda inferior | PreÃ§o prÃ³ximo da banda superior |
| **RSI** | Menor que 49 (sobrevenda) | Maior que 50 (sobrecompra) |
| **EMA_9** | PreÃ§o >= EMA_9 * 0.997 | PreÃ§o <= EMA_9 * 0.999 |
| **MACD** | Acima da linha de sinal e nÃ£o muito negativo | Abaixo da linha de sinal |

Essa estratÃ©gia garante que as compras e vendas sejam feitas com base em tendÃªncias bem definidas, reduzindo o risco de entrar cedo demais em uma operaÃ§Ã£o.

Se precisar de mais ajustes, sÃ³ avisar! ð

