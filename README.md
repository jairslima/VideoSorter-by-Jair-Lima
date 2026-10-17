# VideoSorter by Jair Lima

Move automaticamente os vídeos que foram parar na pasta **Imagens** (por exemplo, por backup de celular) para a pasta **Vídeos**, mantendo a estrutura de subpastas e todas as datas dos arquivos (criação, modificação e acesso).

## Como funciona

- Origem: `%USERPROFILE%\Pictures`. Destino: `%USERPROFILE%\Videos`. Para mudar, edite `SRC` e `DST` no início de `videosorter.py`.
- Extensões: `.mp4 .mov .avi .mkv .wmv .m4v .mts .m2ts .3gp .flv .webm .ts`.
- Se já existir um arquivo com o mesmo nome no destino, acrescenta `_1`, `_2` e assim por diante. Nunca sobrescreve.
- Na mesma unidade, o movimento é uma renomeação atômica que preserva todos os metadados.
- Mantém um log com rotação (5 arquivos de 1 MB) na pasta `logs`.

## Uso

```bash
python videosorter.py            # abre a interface gráfica
pythonw videosorter.py --silent  # sem interface, ideal para o Agendador de Tarefas do Windows
```

Requer Python 3.10 ou superior e Windows (usa Tkinter e uma notificação nativa). Não tem dependências externas.

## Licença

MIT, veja [LICENSE](LICENSE).
