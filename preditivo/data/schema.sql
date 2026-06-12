CREATE TABLE IF NOT EXISTS times (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT UNIQUE NOT NULL,
    nome_canonico TEXT,
    sofascore_id INTEGER,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS partidas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    time_casa_id INTEGER NOT NULL REFERENCES times(id),
    time_fora_id INTEGER NOT NULL REFERENCES times(id),
    data TEXT,
    competicao TEXT,
    gols_casa INTEGER,
    gols_fora INTEGER,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(time_casa_id, time_fora_id, data)
);

CREATE TABLE IF NOT EXISTS estatisticas_detalhadas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    partida_id INTEGER NOT NULL REFERENCES partidas(id),
    escanteios_casa INTEGER,
    escanteios_fora INTEGER,
    cartoes_amarelos_casa INTEGER,
    cartoes_amarelos_fora INTEGER,
    cartoes_vermelhos_casa INTEGER,
    cartoes_vermelhos_fora INTEGER,
    posse_casa REAL,
    posse_fora REAL,
    chutes_gol_casa INTEGER,
    chutes_gol_fora INTEGER,
    faltas_casa INTEGER,
    faltas_fora INTEGER,
    impedimentos_casa INTEGER,
    impedimentos_fora INTEGER,
    xg_casa REAL,
    xg_fora REAL,
    big_chances_casa INTEGER,
    big_chances_fora INTEGER,
    passes_certos_casa INTEGER,
    passes_certos_fora INTEGER,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(partida_id)
);

CREATE TABLE IF NOT EXISTS predicoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    partida_id INTEGER NOT NULL REFERENCES partidas(id),
    modelo TEXT NOT NULL,
    prob_casa REAL,
    prob_empate REAL,
    prob_fora REAL,
    xg_casa REAL,
    xg_fora REAL,
    escanteios_casa REAL,
    escanteios_fora REAL,
    cartoes_casa REAL,
    cartoes_fora REAL,
    prob_over_25 REAL,
    prob_btts REAL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS jogadores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    sofascore_id INTEGER UNIQUE,
    time_id INTEGER REFERENCES times(id),
    posicao TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS estatisticas_jogadores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    partida_id INTEGER NOT NULL REFERENCES partidas(id),
    jogador_id INTEGER NOT NULL REFERENCES jogadores(id),
    minutos INTEGER,
    gols INTEGER,
    assistencias INTEGER,
    cartao_amarelo INTEGER,
    cartao_vermelho INTEGER,
    chutes INTEGER,
    nota REAL,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(partida_id, jogador_id)
);

CREATE INDEX IF NOT EXISTS idx_partidas_data ON partidas(data);
CREATE INDEX IF NOT EXISTS idx_partidas_times ON partidas(time_casa_id, time_fora_id);
CREATE INDEX IF NOT EXISTS idx_stats_jog_partida ON estatisticas_jogadores(partida_id);
