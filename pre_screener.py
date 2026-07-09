def select_best_symbols(symbols, limit=500):
    """
    Placeholder for smart pre-screening.
    For now, keep the app stable by returning the symbols unchanged.
    Next we will make this rank by dollar volume, volume, % change, ATR, and RVOL.
    """
    if limit:
        return symbols[:limit]
    return symbols
