# Manutenção do perfil e integração de dados

## Estrutura

- `docs/TEMPLATE.md`: estrutura e apresentação do README; ponto de edição das seções.
- `data/profile.json`: fatos compartilhados, contatos, stack, educação e critérios de seleção.
- `scripts/update_readme.py`: coleta, valida e gera todos os arquivos. Usa apenas a biblioteca padrão do Python (3.12+).
- `data/github.json`: última consulta real aos repositórios públicos e campos compartilhados de identidade.
- `assets/github-stats.svg` e `assets/languages.svg`: cartões locais sem ícones ou dependência de serviços de estatísticas externos.
- `assets/projects/`: capturas existentes do Sistema de Pedidos e NutriFit, copiadas sem edição do portfólio local, e capas SVG geradas para os outros quatro projetos.
- `README.md`: saída gerada. Alterações diretas são sobrescritas na próxima execução.
- `tests/test_update_readme.py`: verificações de paginação, filtros, renderização e falhas da API.
- `.github/workflows/update-readme.yml`: validação e atualização diária.

## Edição local

Edite o template para mudar a organização ou o texto das seções. Os dados recorrentes ficam em `data/profile.json`, evitando contatos e fatos divergentes. Para visualizar alterações usando a última consulta real:

A apresentação segue esta ordem: identificação e contatos, sobre mim, projetos em destaque, stack, educação e certificações, experiência, projetos recentes, atividade no GitHub, serviços e contato. Competências profissionais e pessoais aparecem no texto sobre o autor. Projetos recentes e métricas usam seções expansíveis nativas, deixando a vitrine de projetos e a formação visíveis primeiro. Edite essa ordem no template, pois o workflow regenera o README a partir dele.

As cores da stack ficam em `badge_colors`, nesse mesmo JSON: cada tecnologia tem uma cor explícita, com tons associados à sua identidade e adaptados para leitura. Conceitos sem marca, como SQL, RAG e testes, usam tons definidos para a apresentação. Ao incluir uma tecnologia em `stack`, cadastre também sua cor hexadecimal; o gerador não aplica mais um cinza silenciosamente quando a cor está ausente.

Os quatro botões de contato têm sua própria paleta em `contact_badge_colors`: Portfólio em azul escuro `1D4ED8`, presente na paleta local do site; LinkedIn em azul `0A66C2`; Instagram em rosa avermelhado `C13558`; E-mail em vermelho `C63D2D`, inspirado no Gmail e escurecido para melhorar o contraste. As cores são sólidas e os tons foram escolhidos para leitura com texto branco. Elas não alteram a paleta da stack.

Os botões de contato usam `for-the-badge`, sem logos, com destinos para Portfólio, LinkedIn, Instagram e E-mail. Cada link inclui um título descritivo para a dica nativa ao passar o mouse. O README não mostra um botão para voltar ao próprio GitHub. Os badges da stack são apenas informativos. Expansão ou animação em hover não é implementada, pois exige CSS/JavaScript personalizado no README.

```powershell
python scripts/update_readme.py --offline
python -m unittest discover -s tests -v
```

Para verificar o consumidor local do portfólio sem acessar a rede ou enviar formulários:

```powershell
node tests/test_portfolio_client.cjs C:/Projetos/challenge-ONE-portfolio/github-projects.js
```

Nesta revisão passaram 19 testes do gerador e 8 testes do consumidor. O workflow deste repositório executa os testes Python; o consumidor pertence ao repositório do portfólio e foi verificado localmente.

Para atualizar os dados pela API pública:

```powershell
python scripts/update_readme.py
```

Sem token, a consulta REST gera repositórios, stars, idade da conta e linguagens. Com `GH_TOKEN` ou `GITHUB_TOKEN` no ambiente, o script tenta também a coleção de contribuições GraphQL dos últimos 12 meses. Não copie tokens para arquivos ou para o portfólio. As métricas complementares são omitidas se a API não permitir a consulta; não se usam zeros ou valores fictícios.

Referência da coleção e dos campos: https://docs.github.com/en/graphql/reference/users#contributionscollection. As métricas representam o período retornado e a visibilidade permitida ao token; não o total histórico de commits. Nomes e dados de repositórios privados não são solicitados pela consulta complementar nem exportados.

O modo offline preserva a data da consulta original. Se a API REST falhar, a geração termina com erro antes de substituir os arquivos. Respostas 429 e 5xx têm tentativas limitadas; 401/403 falham com mensagem clara. Não há fallback que copie variáveis sem resolver.

## Métricas e seleção

- Repositórios: todos os repositórios públicos do proprietário, com paginação, incluindo forks.
- Stars: soma apenas dos repositórios próprios, excluindo forks.
- Linguagens: distribuição da linguagem principal entre os repositórios públicos próprios com linguagem informada. Não é percentual de bytes nem avaliação de proficiência. Essa base substitui a mistura anterior de percentuais por bytes e contagens de apenas 15 repositórios.
- Projetos do README: até seis repositórios próprios, ativos, com pushes mais recentes; exclui este repositório de perfil. A seleção continua automática.
- Projetos do portfólio: permanecem curados localmente; os seis nomes estão registrados em `featured_repositories`. O feed contém os demais projetos também, permitindo consultar seus metadados sem copiar a lista de recentes para os cards.

### Exibição visual no README

`project_showcase`, no JSON de perfil, registra título, descrição, tecnologias, decisões, captura e demo dos projetos selecionados. O template usa `{{ PROJECT_SHOWCASE }}` para essa seção. Os seis projetos aparecem em uma grade de três colunas e duas linhas, feita com tabela HTML nativa do GitHub. Cada card tem imagem ou capa, título, descrição, tecnologias, metadados, decisões expansíveis e botões de acesso. Sistema de Pedidos e NutriFit usam suas capturas reais; os outros quatro usam capas de apresentação SVG com título e tecnologias, não capturas fictícias. A aparência acompanha as bordas e o tema da tabela do GitHub, sem CSS personalizado para reproduzir os fundos, curvas ou animações do site. Em telas estreitas, o GitHub pode oferecer rolagem horizontal da tabela.

As imagens abrem a demo, quando cadastrada, ou o repositório. Os cards sem demo oferecem código e documentação. A descrição técnica abre por clique em `<details>` nativo. Não há API ou JavaScript no README para simular o botão de consulta do site: os metadados já vêm da geração pelo workflow e mostram a coleta real.

Os pushes e stars da vitrine vêm da mesma coleta que alimenta a lista automática de recentes. Se os metadados estiverem ausentes, a apresentação cadastrada continua disponível, sem valores fictícios. As capturas ficam no repositório para não depender do endereço publicado do portfólio.

A lista em **Atualizados recentemente** continua automática. Um projeto novo aparece quando estiver entre os seis pushes mais recentes elegíveis, após a próxima execução diária/manual autorizada; isso não cria automaticamente uma demonstração na vitrine. Para incluir um card, cadastre o projeto em `featured_repositories` e `project_showcase` e gere o README. Uma captura real é opcional: se cadastrada, deve existir em `assets/projects/`; se ausente, o gerador cria uma capa SVG textual. As capturas não são recriadas pelo workflow; precisam ser revisadas e versionadas junto da configuração. As capas SVG são atualizadas com os títulos e tecnologias.

Procedência da apresentação: descrições, decisões e links vieram dos cards em `C:/Projetos/challenge-ONE-portfolio/index.html`; as duas capturas vieram de `assets/projeto-pedidos.png` e `assets/projeto-nutrifit.png`, já documentadas em `CONTENT_SOURCES.md` daquele projeto. A versão desta seção não confirma a disponibilidade atual das demos e não inclui uma demo de Filmes AWS cuja disponibilidade estava pendente na fonte. Os metadados mantêm a data da última coleta real.

## Integração com o portfólio

O consumidor local em `C:/Projetos/challenge-ONE-portfolio/github-projects.js` consulta:

`https://raw.githubusercontent.com/MarceloRodrigues1853/MarceloRodrigues1853/main/data/github.json`

Ao clicar em **Consultar dados sincronizados**, ele valida versão, proprietário e data do feed, atualiza nome, foco profissional, links públicos de contato e metadados dos cards (push, linguagem, stars e arquivamento). Preserva layout, seleção editorial, descrições técnicas, imagens, demos e credenciais com suas fontes. O formulário e sua configuração de envio permanecem locais; alterar o endereço no JSON não reconfigura o serviço do formulário.

Se o feed não carregar ou um registro estiver incompleto, consulta a API pública diretamente para os metadados dos projetos. Se ambas as consultas falharem, mantém o conteúdo estático e informa o resultado. A data apresentada é a coleta real do feed, não a data de acesso à página. Nenhum conteúdo é bloqueado por JavaScript ou pela rede.

O fluxo usa uma fonte compartilhada para os campos acima: GitHub + `profile.json` geram README e JSON; o portfólio consome esse JSON. Não há escrita automática do navegador de volta ao repositório. Mudanças editoriais de identidade devem ser feitas nessa fonte e revisadas nos dois projetos. Formação detalhada, credenciais e descrições do portfólio continuam em HTML local, preservando fontes e diferenças de apresentação.

**A integração publicada ainda depende de revisão e autorização separadas para publicar os dois repositórios.** Até o JSON existir no GitHub, a alternativa pela API direta mantém o portfólio funcionando.

## Workflow proposto

- Execução diária às 09h de Brasília (12h UTC); o GitHub pode atrasar a execução na fila.
- `workflow_dispatch` permite atualização manual apenas na branch padrão.
- Pull requests executam testes e geração offline com permissões de leitura; não publicam.
- A atualização remota gera README, JSON e SVGs em uma única etapa. Não há `git pull` que oculte erros nem substituições em `awk` sobre marcadores incompatíveis.
- `cancel-in-progress: false` evita cancelar uma geração já iniciada no mesmo grupo.
- Uma falha de geração interrompe o job antes do commit.
- O push comum não reescreve histórico; se a branch avançar durante a execução, o job falha em vez de forçar a publicação.

**Publicação automática:** assim como no workflow anterior, as execuções agendadas/manuais propõem commit e push na branch padrão. A proposta passa a incluir `README.md`, `data/github.json`, os dois SVGs de estatísticas e as capas SVG em `assets/projects/`. Isso precisa ser revisado e expressamente autorizado antes de publicar o workflow. Nenhum workflow remoto foi disparado durante esta preparação.

## Diagnóstico desta revisão — 06/10/2026

As capturas mostram marcadores de template visíveis, dados duplicados e divergentes, e imagens externas quebradas.

A execução https://github.com/MarceloRodrigues1853/MarceloRodrigues1853/actions/runs/37367505970 consta como `failure`; seu job foi retornado como `cancelled`, sem etapas, e os logs retornaram 404. Isso não comprova uma falha na action de estatísticas. A execução anterior, https://github.com/MarceloRodrigues1853/MarceloRodrigues1853/actions/runs/37216299657, concluiu todas as etapas com sucesso.

Problemas verificáveis no código anterior:

- O fallback substituía apenas idade, repositórios e commits, deixando stars, issues, PRs e reviews sem resolução.
- O `awk` mantinha os marcadores `{{ REPOSITORIES_TEMPLATE... }}` no texto publicado.
- A action de estatísticas e as etapas posteriores tinham critérios distintos para linguagens e projetos.
- `curl -s` não tratava erros HTTP; a resposta de erro poderia chegar ao `jq` como se fosse lista de repositórios.
- `grep -v null` com `pipefail` podia encerrar o job se nenhuma linguagem fosse encontrada.
- `git pull ... || echo` mascarava erros de sincronização.

A geração única elimina esses problemas locais. A causa exata do último cancelamento permanece não confirmada e o novo fluxo ainda precisa ser validado no GitHub após autorização.

## Revisão antes de versionar

Confira diff, arquivos gerados e aparência. Autorizações para `git add`, commit, push, PR, merge ou deploy são separadas. O consumidor do portfólio está em outra branch/projeto e sua publicação pode acionar o fluxo Vercel; o destino e esse efeito devem ser conferidos antes do envio.
