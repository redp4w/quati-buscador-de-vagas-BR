# Busca e compatibilidade

## Dois modos de pesquisa

**Busca livre** aceita até cinco cargos, uma frase adicional e filtros escolhidos na hora. A frase
é enviada inteira para cada portal. Em páginas gerais de empresas, a conferência local aceita a
frase completa ou a cobertura das palavras relevantes como palavras inteiras; artigos e
preposições são ignorados. Fragmentos arbitrários não contam.

Quando há mais de um cargo, o Q.U.A.T.I. cria uma consulta separada para cada um. Por exemplo,
`Segurança da informação` e `Analista de suporte` não viram uma única consulta misturada.

**Compatíveis com o Perfil** exige:

- cargos de interesse;
- níveis desejados;
- competências ou experiência;
- modalidades de trabalho;
- cidade-base, exceto quando a única modalidade aceita é Remoto.

O app usa os cargos do Perfil para descobrir vagas, calcula a nota localmente e mostra apenas as
que atingem **70% ou mais**. Nenhum texto do Perfil é enviado aos portais.

## Fórmula atual

A nota é uma média ponderada, limitada a 100 pontos:

```text
compatibilidade = 35% cargo + 25% senioridade + 25% competências
                  + 15% localização/modalidade
```

Cargo usa famílias profissionais e proximidade textual; competências usam termos profissionais em
comum; localização considera modalidade e distância numa base geográfica offline. A senioridade
também aplica tetos: uma vaga um nível acima fica limitada a 70%; dois ou mais níveis acima, a 45%.
Quando o anúncio omite dados, a explicação indica a incerteza em vez de inventar uma correspondência.

O corte de 70% é uma regra de produto, não uma probabilidade de contratação. A nota serve para
triagem e não substitui a leitura do anúncio.

## Bases ocupacionais que podem enriquecer o cálculo

O recurso já funciona sem baixar um repositório externo. Para uma evolução sem modelo generativo,
as melhores fontes avaliadas são:

| Base | Vantagem | Cuidado de integração |
|---|---|---|
| [CBO — Ministério do Trabalho e Emprego](https://www.gov.br/trabalho-e-emprego/pt-br/assuntos/cbo/servicos/downloads) | classificação brasileira oficial de ocupações | ótima para códigos, títulos e sinônimos; não oferece sozinha uma nota detalhada de competências |
| [ESCO — Comissão Europeia](https://esco.ec.europa.eu/en/use-esco) | relaciona ocupações e competências essenciais/opcionais; possui API e downloads em português | precisa de mapeamento entre títulos brasileiros, CBO e ESCO |
| [O*NET Database](https://www.onetcenter.org/database.html) | oferece títulos alternativos, habilidades, tecnologia e avaliações numéricas por ocupação | conteúdo centrado no mercado dos EUA e principalmente em inglês |

Uma próxima versão pode representar Perfil e vaga como vetores de competências e usar
**similaridade do cosseno**, dando mais peso a competências raras e essenciais. A pontuação
ocupacional continuaria separada para não permitir que muitas palavras genéricas compensem um
cargo incompatível. Antes disso, o projeto precisa versionar os dados, documentar licenças e criar
uma tabela CBO ↔ ESCO/O*NET validada para o português do Brasil.

## O que a busca textual significa

- `Segurança da informação` segue como uma frase única no endereço de pesquisa do portal.
- O comportamento do portal pode variar: alguns procuram a frase, outros aplicam as palavras.
- Nas páginas que o próprio Q.U.A.T.I. precisa filtrar, a frase exata tem prioridade; sem ela, o
  app mede a cobertura de palavras relevantes completas.
- Vários cargos são pesquisados individualmente, com limite de cinco para evitar excesso de
  requisições.
