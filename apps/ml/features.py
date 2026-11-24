from apps.game.catalog import COLUMNAS, FEATURES, IDS, STATS, TARGET, TIPOS, atributos


def fila_combate(primero, segundo):
    return {f'{campo}_{lado}': valor
            for lado, criatura in enumerate((primero, segundo), start=1)
            for campo, valor in atributos(criatura).items()}
