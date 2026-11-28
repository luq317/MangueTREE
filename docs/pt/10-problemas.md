# Problemas comuns

**Cabeçalho não encontrado.** A folha precisa ter, nas 25 primeiras linhas, uma linha com identificador da árvore, espécie, DAP e condição. Compare com a planilha modelo.

**Colunas que faltam.** A mensagem diz quais colunas faltam e quais nomes são aceitos (por exemplo `DAP`, `dbh_cm`, `Status` para a condição). Em CSV ou TXT, o aplicativo tenta `;`, `,` e tabulação se o separador escolhido não separar as colunas.

**Nenhum tronco ficou para o cálculo.** Todos os DAP estão vazios ou inválidos, ou as condições não são reconhecidas. A tabela abaixo da mensagem lista cada problema. Se o DAP é fórmula, abra o arquivo no Excel e salve de novo.

**Aviso de unidade convertida.** O cabeçalho dizia mm, cm ou ha e o aplicativo converteu. Confira se a conversão é a esperada.

**Muitas espécies desconhecidas.** Confira a região no menu lateral ou acrescente os apelidos que você usa na tabela de espécies.

**Aviso de área.** A planilha não tem a área da parcela. Escreva o rótulo e o valor no cabeçalho da folha ou informe a área no menu lateral.

**Tronco com DAP e sem condição.** Escolha se ele deve ser excluído, contado como vivo ou como morto.

**Espécie ambígua (`Rh`, `Pe`).** Use o código da espécie (`Rm`, `As`...) ou cadastre um apelido na tabela de espécies.

**Etiquetas repetidas ou número de troncos diferente do declarado.** São avisos: confira a planilha de campo.

**Um ano aparece duas vezes na análise temporal.** Os valores são tirados em média. Confira se não há folhas repetidas.

**O CSV abre com as colunas grudadas.** Use o arquivo Excel ou o TXT.

**Uma mudança no código não aparece (rodando do código).** Instale em modo editável (`pip install -e .`) e reinicie o aplicativo.

A lista completa das verificações está em [Formato dos dados](../data-format.md#validation).
