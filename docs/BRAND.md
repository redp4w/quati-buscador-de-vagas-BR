# Identidade visual

## Conceito

**Q.U.A.T.I.** é a forma oficial do nome exibido. A pontuação evidencia a sigla, enquanto o
pacote técnico continua como `quati`. A expansão é **Query Unificada de Anúncios de Trabalho na Internet** e o
subtítulo público é **Buscador de vagas públicas BR**.

O mascote é um quati brasileiro sem roupa ou acessórios, com máscara facial clara, cauda anelada e
silhueta de alto contraste. O desenho combina curiosidade, busca e tecnologia sem recorrer a
símbolos genéricos de recrutamento. A assinatura usa letras bitmap brancas e pequenos quadrados
vermelhos entre as iniciais. A interface segue uma leitura contemporânea dos keygens e demos do
começo dos anos 2000: superfícies escuras, cantos quadrados, brilho contido, linhas de varredura e
tipografia monoespaçada, sem prejudicar a leitura.

Os arquivos principais são imagens de alta resolução. A aplicação usa versões próprias para a
barra lateral, a página inicial, o ícone do navegador e o banner do GitHub.

## Paleta

| Uso | Cor |
|---|---|
| Preto principal | `#060807` |
| Preto do menu | `#020303` |
| Grafite/terminal | `#10150F` |
| Vermelho ação | `#FF1738` |
| Verde fósforo | `#A8FF60` |
| Ciano de link | `#72F4FF` |
| Texto | `#E6F6DF` |
| Borda | `#3A5232` |

## Arquivos

| Arquivo | Aplicação |
|---|---|
| `src/quati/assets/quati-icon-master.png` | matriz original do símbolo |
| `src/quati/assets/quati-horizontal-master.png` | matriz original da assinatura horizontal |
| `src/quati/assets/quati-mascot-master.png` | matriz original do mascote de corpo inteiro |
| `src/quati/assets/quati-inicio-master.gif` | fonte aprovada da composição vertical |
| `src/quati/assets/quati-horizontal-white.png` | assinatura horizontal transparente |
| `src/quati/assets/quati-mascot.png` | mascote limpo e transparente |
| `src/quati/assets/quati-menu-scan.gif` | assinatura horizontal animada usada no menu |
| `src/quati/assets/quati-inicio-scan.gif` | assinatura vertical animada usada no acesso |
| `src/quati/assets/quati-walk-master.gif` | matriz original com as oito poses ordenadas da caminhada |
| `src/quati/assets/quati-solo-scan.gif` | mascote animado em alta resolução |
| `src/quati/assets/quati-loading.gif` | ciclo real de caminhada exibido durante a coleta de vagas |
| `src/quati/assets/quati-icon-approved.png` | versão aprovada do ícone em alta resolução |
| `src/quati/assets/quati-icon.png` | atalhos Linux e superfícies raster |
| `src/quati/assets/quati-icon.ico` | atalhos Windows |
| `docs/assets/github-social-preview.png` | imagem social do repositório |
| `docs/assets/app-access.png` | captura sintética do primeiro acesso |
| `docs/assets/workflow.svg` | fluxo principal do README |

## Regras de uso

- Preserve proporção, cores e espaço livre.
- Use fundos simples e com contraste.
- Não redesenhe o mascote nem altere a proporção da cauda.
- Use o vermelho em ações principais e nos separadores da assinatura.
- Prefira preto e vermelho na navegação; verde-fósforo e ciano ficam restritos ao corpo e a estados.
- No menu preto, use somente a assinatura branca/vermelha com fundo transparente.
- No menu, o desenho permanece imóvel e apenas a varredura aprovada se move.
- No acesso, a luz psicodélica fica restrita ao interior do logo; pequenos blocos se deslocam e
  retornam rapidamente, sem scanner externo, pulso global ou deformação do desenho.
- No carregamento, as oito poses formam uma caminhada legível e contínua, sem efeitos que ocultem
  o movimento das pernas.
- Todos os GIFs devem ter fundo realmente transparente e reprodução contínua.
- Use fontes do sistema. A interface não baixa fontes nem rastreadores.

## Reprodução dos assets

Os arquivos derivados são reconstruídos a partir dos masters com:

```text
uv run --extra dev python tools/build_brand_assets.py
```

O gerador também atualiza a imagem social do GitHub e reserva um índice de transparência nos GIFs.

## GitHub

Envie `docs/assets/github-social-preview.png` em **Settings → General → Social preview**.

Descrição curta sugerida:

> Central local e open source para pesquisar vagas públicas no Brasil, comparar compatibilidade e
> preparar currículos para candidatura manual.

Tópicos: `jobs`, `brazil`, `python`, `streamlit`, `playwright`, `privacy`, `sqlite`,
`resume-builder`.

## Licença da marca

A licença MIT cobre o código. Nome, símbolo e arquivos visuais seguem
`BRAND_ASSET_LICENSE.md`, que permite redistribuir cópias oficiais sem transformar a marca em um
produto diferente.
