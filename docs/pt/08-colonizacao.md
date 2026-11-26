# Colonização

Esta página estuda a regeneração (jovens) com as planilhas de colonização do NEMA/UERJ, uma por parcela. Ela é uma **prévia**: fica oculta no menu até ser ativada.

## Como ativar

No terminal, dentro da pasta do projeto:

```
PYTHONPATH=src MANGUETREE_COLONIZACAO=1 streamlit run src/manguetree/app/Home.py
```

No Streamlit Cloud, crie o segredo `colonizacao = true` nas configurações do aplicativo.

## Como subir as planilhas

Envie uma planilha `.xlsx` por parcela e clique em **Executar análise** no menu lateral. O aplicativo identifica as coletas e o ano de cada uma, padroniza os códigos e mostra uma verificação. Você pode corrigir um ano e reclassificar códigos.

## As abas

**Gráficos**, com as subabas:

- **Densidade:** curva da densidade de jovens por parcela e composição por espécie, com as tabelas logo abaixo.
- **Altura:** altura dos jovens por parcela, com o painel das coletas de cada ano e a tabela abaixo.
- **Idade:** densidade contra a idade da parcela (0 a 10 anos), linear ou logarítmica, com curva ajustada e equação opcionais.
- **Cruzamento:** altura e densidade, em linhas pelos anos ou em dispersão com a reta e a equação.
- **Contagem por coorte:** indivíduos por ano empilhados por coorte, espécie ou item, com menu de cores.
- **Esquema de Jiménez:** esquema do desenvolvimento do povoamento ao lado da densidade observada.

**Verificação.** Coletas e anos identificados, códigos por ano, registros, espécies e alertas de altura.

**Exportar.** Tabelas limpas (formato longo e largo) em CSV e Excel.
