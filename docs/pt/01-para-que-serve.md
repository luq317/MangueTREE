# Para que serve o MangueTREE

O MangueTREE lê a planilha de campo de uma parcela de manguezal e calcula, em segundos, os parâmetros estruturais e fitossociológicos que costumam ser feitos à mão em planilhas. Ele foi criado no Núcleo de Estudos em Manguezais da UERJ (NEMA/UERJ) e segue o protocolo do núcleo, mas aceita planilhas de outros grupos desde que tenham as colunas básicas.

## O que ele calcula

- **Estrutura:** densidade (troncos por hectare), área basal, DAP médio, altura média e altura do dossel, número de espécies, mortalidade em troncos e em área basal, número de troncos por árvore.
- **Fitossociologia:** densidade relativa (DR%), dominância relativa (DoR%), frequência relativa (FR%, com várias parcelas) e valor de importância (IVI).
- **Classes de DAP:** densidade e área basal por classe, histograma e quociente de De Liocourt.
- **Complexidade:** índice de complexidade de Holdridge.
- **Altura:** relação altura × DAP por espécie e perfil vertical da parcela.
- **Várias parcelas:** comparação entre parcelas e IVI com as parcelas como unidades amostrais.
- **Vários anos:** evolução de qualquer parâmetro, por espécie e a mortalidade ao longo do tempo.
- **Colonização:** densidade e altura de jovens, idade da parcela, cruzamento altura × densidade e contagem por coorte (versão de prévia).

As fórmulas, as convenções e as fontes estão na página [Métodos](../methods.md).

## O que ele não faz

- Não corrige a planilha: ele avisa o que está estranho (aba **Verificação dos dados**), mas não troca valores sozinho.
- Não substitui a leitura crítica dos resultados. Um valor por hectare muda se a área da parcela estiver errada, por exemplo.
- Com uma só parcela não existe frequência relativa nem IVI completo. Para o IVI, use [Múltiplas parcelas](06-multiplas-parcelas.md).

## Onde ficam os seus dados

O aplicativo roda no seu computador. Na versão para Windows e macOS, nenhum dado sai da sua máquina e não é preciso internet, nem para gerar o relatório em PDF.

## Como citar

Pereira LS, Motta LL, Matta TC, Chaves FO, Soares MLG (2026). MangueTREE v1.3.1. https://github.com/luq317/MangueTREE. A página inicial do aplicativo e o [README](https://github.com/luq317/MangueTREE/blob/main/README.md) trazem a citação completa e o BibTeX. Os cálculos se baseiam em Cintrón e Schaeffer-Novelli, Pool et al. e Estrada et al. (2013, Aquatic Botany 111:135-143).
