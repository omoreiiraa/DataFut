import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import locale

HOME_ADVANTAGE = 1.10
COMPETITION_ID = "BSA"

requests.packages.urllib3.disable_warnings()

try:
    locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_TIME, 'Portuguese_Brazil')
    except locale.Error:
        st.warning("Não foi possível configurar o locale 'pt_BR'. Os dias da semana podem aparecer em inglês.")


class FootballAPIClient:
    BASE_URL = "https://api.football-data.org/v4"

    def __init__(self, api_key: str):
        self.headers = {"X-Auth-Token": api_key}

    def _make_request(self, endpoint, params=None):
        try:
            response = requests.get(f"{self.BASE_URL}/{endpoint}", headers=self.headers, params=params, verify=False)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            st.error(f"Erro de conexão com a API: {e}")
            return None

    def _process_matches_to_df(self, match_list):
        if not match_list:
            return pd.DataFrame()

        processed_list = []
        for match in match_list:
            status = match.get('status')
            score = match.get('score', {})
            fullTime = score.get('fullTime', {})

            processed_list.append({
                'id': match['id'],
                'Rodada': match.get('matchday'),
                'Data': match.get('utcDate'),
                'Status': status,
                'Mandante': match['homeTeam']['name'], 'Visitante': match['awayTeam']['name'],
                'MandanteID': match['homeTeam']['id'], 'VisitanteID': match['awayTeam']['id'],
                'Gols Mandante': fullTime.get('home'),
                'Gols Visitante': fullTime.get('away'),
                'Vencedor': score.get('winner'),
                'Estadio': match.get('venue'),
                'Competicao': match.get('competition', {}).get('name', 'N/A')
            })
        df = pd.DataFrame(processed_list)
        if df.empty: return pd.DataFrame()
        df['Data'] = pd.to_datetime(df['Data'], utc=True)
        df['Rodada'] = df['Rodada'].fillna(0).astype(int)
        return df

    @st.cache_data(ttl=3600)
    def get_standings(_self, competition_id: str):
        data = _self._make_request(f"competitions/{competition_id}/standings")
        if not data or not data.get('standings'): return pd.DataFrame()
        table = data['standings'][0]['table']
        return pd.DataFrame([{'Pos': item['position'], 'Club': item['team']['crest'], 'Time': item['team']['name'],
                              'P': item['points'], 'J': item['playedGames'], 'V': item['won'], 'E': item['draw'], 'D': item['lost'],
                              'GF': item['goalsFor'], 'GC': item['goalsAgainst'], 'SG': item['goalDifference'],
                              'id': item['team']['id']} for item in table])

    @st.cache_data(ttl=3600)
    def get_scorers(_self, competition_id: str):
        data = _self._make_request(f"competitions/{competition_id}/scorers")
        if not data or not data.get('scorers'): return pd.DataFrame()
        player_stats = []
        for scorer in data.get('scorers', []):
            player_stats.append({
                'Jogador': scorer['player']['name'], 'Time': scorer['team']['name'],
                'Gols': scorer.get('goals', 0), 'Assistências': scorer.get('assists', 0),
                'Pênaltis': scorer.get('penalties', 0),
            })
        return pd.DataFrame(player_stats)

    @st.cache_data(ttl=300)
    def get_head2head(_self, team1_id: int, team2_id: int):
        data1 = _self._make_request(f"teams/{team1_id}/matches?opponent={team2_id}")
        data2 = _self._make_request(f"teams/{team2_id}/matches?opponent={team1_id}")

        matches1 = data1.get('matches', []) if data1 else []
        matches2 = data2.get('matches', []) if data2 else []

        all_matches_dict = {match['id']: match for match in matches1}
        for match in matches2:
            if match['id'] not in all_matches_dict:
                all_matches_dict[match['id']] = match

        return list(all_matches_dict.values())

    @st.cache_data(ttl=300)
    def get_matches(_self, competition_id: str):
        data = _self._make_request(f"competitions/{competition_id}/matches")
        if not data or not data.get('matches'):
            return pd.DataFrame()
        return _self._process_matches_to_df(data.get('matches', []))

    @st.cache_data(ttl=300)
    def get_team_matches(_self, team_id: int):
        data = _self._make_request(f"teams/{team_id}/matches")
        if not data or not data.get('matches'):
            return pd.DataFrame()
        return _self._process_matches_to_df(data.get('matches', []))

def page_key_metrics(client, competition_id):
    st.subheader("📊 Estatísticas Gerais", anchor=False)

    with st.spinner("Carregando estatísticas..."):
        standings_data = client.get_standings(competition_id)
        scorers_data = client.get_scorers(competition_id)

    if standings_data.empty: st.warning("Não foi possível carregar as estatísticas de classificação."); return
    if scorers_data.empty: st.warning("Não foi possível carregar as estatísticas de artilharia."); return

    try:
        lider = standings_data.iloc[0]
        lider_nome = lider['Time']
        lider_pontos = f"{lider['P']} pontos"

        artilheiro = scorers_data.sort_values(by='Gols', ascending=False).iloc[0]
        artilheiro_nome = artilheiro['Jogador']
        artilheiro_gols = f"{artilheiro['Gols']} gols"

        melhor_ataque = standings_data.sort_values(by='GF', ascending=False).iloc[0]
        ataque_nome = melhor_ataque['Time']
        ataque_gols = f"{melhor_ataque['GF']} gols marcados"

        melhor_defesa = standings_data.sort_values(by='GC', ascending=True).iloc[0]
        defesa_nome = melhor_defesa['Time']
        defesa_gols = f"{melhor_defesa['GC']} gols sofridos"

    except (IndexError, KeyError) as e:
        st.error(f"Erro ao processar as estatísticas: {e}. Verifique os dados da API.")
        return

    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric(label="🏆 Líder do Campeonato", value=lider_nome, delta=lider_pontos)
    with col2: st.metric(label="🎯 Maior Artilheiro", value=artilheiro_nome, delta=artilheiro_gols)
    with col3: st.metric(label="🔥 Melhor Ataque", value=ataque_nome, delta=ataque_gols)
    with col4: st.metric(label="🛡️ Melhor Defesa", value=defesa_nome, delta=defesa_gols)

def style_position(pos):
    if pos <= 4: return 'background-color: #1DB954; color: white; border-radius: 4px; text-align: center; font-weight: bold;'
    elif pos <= 6: return 'background-color: #86C024; color: white; border-radius: 4px; text-align: center; font-weight: bold;'
    elif pos <= 12: return 'background-color: #3498DB; color: white; border-radius: 4px; text-align: center; font-weight: bold;'
    elif pos >= 17: return 'background-color: #E74C3C; color: white; border-radius: 4px; text-align: center; font-weight: bold;'
    else: return 'background-color: #333333; color: white; border-radius: 4px; text-align: center; font-weight: bold;'

def page_standings(client, competition_id):
    st.markdown("<div class='table-title'>Classificação Brasileirão Série A</div>", unsafe_allow_html=True)
    with st.spinner("Carregando classificação..."):
        standings = client.get_standings(competition_id)
        if not standings.empty:
            standings['Time'] = standings.apply(
                lambda row: f'<img src="{row["Club"]}" style="height: 22px; vertical-align: middle; margin-right: 8px;"> {row["Time"]}',
                axis=1
            )
            cols_order = ['Pos', 'Time', 'P', 'J', 'V', 'E', 'D', 'GF', 'GC', 'SG']
            standings_display = standings[cols_order]
            styler = standings_display.style.apply(lambda s: s.map(style_position), subset=['Pos'])
            styler = styler.format({'Time': None}).hide(axis="index")
            st.markdown(
                f"<div class='standings-table-container'>{styler.to_html(escape=False)}</div>",
                unsafe_allow_html=True
            )
            st.markdown("""
            <div class="rules-container">
                <h3>Regras</h3>
                <ul>
                    <li><span class="dot green"></span> Taça Libertadores</li>
                    <li><span class="dot light-green"></span> Copa Libertadores Qualificação</li>
                    <li><span class="dot blue"></span> Taça Sul Americana</li>
                    <li><span class="dot red"></span> Rebaixamento</li>
                </ul>
                <div class="tie-breaker">
                    <p>No caso de duas (ou mais) equipes terem o mesmo número de pontos, aplicam-se as seguintes regras:</p>
                    <p>1. Número de vitórias</p><p>2. Saldo de Gols</p><p>3. Gols marcados</p>
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.warning("Não foi possível carregar a classificação.")

def page_team_analysis(client, competition_id):
    st.header("Análise de Times (Confronto Direto)", anchor=False)

    with st.spinner("Carregando times..."):
        standings = client.get_standings(competition_id)

    if standings.empty:
        st.warning("Não foi possível carregar os times.")
        return

    team_dict = pd.Series(standings.id.values, index=standings.Time).to_dict()
    team_crests = pd.Series(standings.Club.values, index=standings.Time).to_dict()

    col1, col2 = st.columns(2)
    with col1:
        team1_name = st.selectbox("Selecione o Time 1", options=standings['Time'], index=0)
    with col2:
        team2_name = st.selectbox("Selecione o Time 2", options=standings['Time'], index=1)

    if st.button("Analisar Confronto", use_container_width=True):
        if team1_name == team2_name:
            st.error("Por favor, selecione dois times diferentes.")
        else:
            team1_id = team_dict[team1_name]
            team2_id = team_dict[team2_name]

            with st.spinner("Analisando confrontos e partidas dos times..."):
                h2h_matches_raw = client.get_head2head(team1_id, team2_id)
                team1_matches_df = client.get_team_matches(team1_id)
                team2_matches_df = client.get_team_matches(team2_id)

            wins_team1, wins_team2, draws = 0, 0, 0
            finished_h2h = [m for m in h2h_matches_raw if m['status'] == 'FINISHED']

            if finished_h2h:
                for match in finished_h2h:
                    if match['score']['winner'] == 'HOME_TEAM':
                        if match['homeTeam']['id'] == team1_id: wins_team1 += 1
                        else: wins_team2 += 1
                    elif match['score']['winner'] == 'AWAY_TEAM':
                        if match['awayTeam']['id'] == team1_id: wins_team1 += 1
                        else: wins_team2 += 1
                    elif match['score']['winner'] == 'DRAW':
                        draws += 1

            crest1 = team_crests.get(team1_name, "")
            crest2 = team_crests.get(team2_name, "")

            c1, c2, c3, c4, c5 = st.columns([2.5, 1, 1.5, 1, 2.5])
            with c1: st.markdown(f"<div class='team-name home'>{team1_name}</div>", unsafe_allow_html=True)
            with c2: st.image(crest1, width=36)
            with c3: st.markdown(f"<div class='match-score-display'>{wins_team1} x {wins_team2}</div>", unsafe_allow_html=True)
            with c4: st.image(crest2, width=36)
            with c5: st.markdown(f"<div class='team-name away'>{team2_name}</div>", unsafe_allow_html=True)

            total_matches = wins_team1 + wins_team2 + draws
            st.markdown(f"<div class='match-info'>Total de {total_matches} confrontos finalizados • {draws} empates</div>", unsafe_allow_html=True)
            st.divider()

            st.subheader("Partidas Recentes", anchor=False)
            tab_team1, tab_team2 = st.tabs([f"Partidas de {team1_name}", f"Partidas de {team2_name}"])

            with tab_team1:
                with st.container(border=True, height=600):
                    if team1_matches_df.empty:
                        st.info(f"Nenhuma partida encontrada para {team1_name}.")
                    else:
                        recent_matches_t1 = team1_matches_df.sort_values(by='Data', ascending=False).head(30)
                        render_match_list(recent_matches_t1, team_crests)

            with tab_team2:
                with st.container(border=True, height=600):
                    if team2_matches_df.empty:
                        st.info(f"Nenhuma partida encontrada para {team2_name}.")
                    else:
                        recent_matches_t2 = team2_matches_df.sort_values(by='Data', ascending=False).head(30)
                        render_match_list(recent_matches_t2, team_crests)


def calculate_match_prediction(home_team_name, away_team_name, standings_df):
    try:
        avg_goals_home = standings_df['GF'].sum() / standings_df['J'].sum()
        avg_goals_away = standings_df['GC'].sum() / standings_df['J'].sum()

        home_team = standings_df[standings_df['Time'] == home_team_name].iloc[0]
        away_team = standings_df[standings_df['Time'] == away_team_name].iloc[0]

        home_attack_strength = (home_team['GF'] / home_team['J']) / avg_goals_home
        home_defense_strength = (home_team['GC'] / home_team['J']) / avg_goals_away
        away_attack_strength = (away_team['GF'] / away_team['J']) / avg_goals_away
        away_defense_strength = (away_team['GC'] / away_team['J']) / avg_goals_home

        exp_goals_home = home_attack_strength * away_defense_strength * HOME_ADVANTAGE
        exp_goals_away = away_attack_strength * home_defense_strength

        total_strength = exp_goals_home + exp_goals_away

        draw_prob = 1 - (abs(exp_goals_home - exp_goals_away) / total_strength)
        draw_prob = max(0.20, min(0.35, draw_prob * 0.5))

        home_win_prob = (exp_goals_home / total_strength) * (1 - draw_prob)
        away_win_prob = (exp_goals_away / total_strength) * (1 - draw_prob)

        total_prob = home_win_prob + draw_prob + away_win_prob

        return {
            'home': int((home_win_prob / total_prob) * 100),
            'draw': int((draw_prob / total_prob) * 100),
            'away': int((away_win_prob / total_prob) * 100)
        }

    except (IndexError, ZeroDivisionError, KeyError):
        return None

def render_match_list(matches_df, team_crests, standings_df=None):
    if matches_df.empty:
        st.info("Nenhuma partida encontrada para esta seleção.")
        return

    for _, row in matches_df.iterrows():
        try:
            data_local = row['Data'].tz_convert('America/Sao_Paulo')
            data_str = data_local.strftime('%d/%m')
            dia_semana = data_local.strftime('%A').capitalize()
            hora_str = data_local.strftime('%H:%M')
        except Exception:
            data_str = row['Data'].strftime('%d/%m')
            dia_semana = row['Data'].strftime('%A').capitalize()
            hora_str = row['Data'].strftime('%H:%M (UTC)')

        info_str = f"{data_str} • {dia_semana} • {hora_str}"
        
        if 'Competicao' in row and row['Competicao'] != 'N/A' and row['Competicao'] != 'Campeonato Brasileiro Série A':
             info_str = f"🏆 {row['Competicao']} • {info_str}"

        st.markdown(f"<div class='match-info'>{info_str}</div>", unsafe_allow_html=True)

        crest_home = team_crests.get(row['Mandante'], "")
        crest_away = team_crests.get(row['Visitante'], "")

        if row['Status'] == 'FINISHED':
            score_home = int(row['Gols Mandante'])
            score_away = int(row['Gols Visitante'])
        elif row['Status'] in ('IN_PLAY', 'PAUSED'):
            score_home = int(row['Gols Mandante']) if pd.notna(row['Gols Mandante']) else 0
            score_away = int(row['Gols Visitante']) if pd.notna(row['Gols Visitante']) else 0
        else:
            score_home = " "
            score_away = " "

        col1, col2, col3, col4, col5 = st.columns([2.5, 1, 1.5, 1, 2.5])
        with col1: st.markdown(f"<div class='team-name home'>{row['Mandante']}</div>", unsafe_allow_html=True)
        with col2:
            if crest_home: st.image(crest_home, width=36)
        with col3: st.markdown(f"<div class='match-score-display'>{score_home} x {score_away}</div>", unsafe_allow_html=True)
        with col4:
            if crest_away: st.image(crest_away, width=36)
        with col5: st.markdown(f"<div class='team-name away'>{row['Visitante']}</div>", unsafe_allow_html=True)


        if row['Status'] in ('SCHEDULED', 'TIMED') and standings_df is not None:
            prediction = calculate_match_prediction(row['Mandante'], row['Visitante'], standings_df)

            if prediction:
                st.markdown(f"""
                <div class="prediction-bar-container">
                    <div class="pred-label home">Vit. {row['Mandante']} ({prediction['home']}%)</div>
                    <div class="pred-label draw">Empate ({prediction['draw']}%)</div>
                    <div class="pred-label away">Vit. {row['Visitante']} ({prediction['away']}%)</div>
                </div>
                <div class="prediction-bar">
                    <div class="bar-home" style="width: {prediction['home']}%;"></div>
                    <div class="bar-draw" style="width: {prediction['draw']}%;"></div>
                    <div class="bar-away" style="width: {prediction['away']}%;"></div>
                </div>
                """, unsafe_allow_html=True)

        st.divider()


def page_matches(client, competition_id):
    with st.spinner("Carregando calendário de partidas..."):
        all_matches = client.get_matches(competition_id)
    if all_matches.empty:
        st.warning("Não foi possível carregar as partidas.")
        return

    with st.spinner("Carregando times..."):
        standings = client.get_standings(competition_id)
    if standings.empty:
        st.warning("Não foi possível carregar dados dos times para os escudos.")
        team_crests = {}
    else:
        team_crests = pd.Series(standings.Club.values, index=standings.Time).to_dict()

    rodadas = sorted(all_matches[all_matches['Rodada'] > 0]['Rodada'].unique())
    if not rodadas:
         st.warning("Nenhuma rodada numerada encontrada.")
         return

    if 'rodada_select' not in st.session_state:
        today = pd.Timestamp.now(tz='UTC')
        next_matches = all_matches[(all_matches['Data'] > today) & (all_matches['Rodada'] > 0)].sort_values(by='Data')

        default_rodada = rodadas[0]
        if not next_matches.empty:
            default_rodada_candidate = int(next_matches.iloc[0]['Rodada'])
            if default_rodada_candidate in rodadas:
                default_rodada = default_rodada_candidate
        elif all_matches['Status'].str.contains('FINISHED').any():
             default_rodada = rodadas[-1]
        st.session_state.rodada_select = default_rodada

    def prev_rodada():
        try:
            current_index = rodadas.index(st.session_state.rodada_select)
            if current_index > 0:
                st.session_state.rodada_select = rodadas[current_index - 1]
        except ValueError:
            st.session_state.rodada_select = rodadas[0]

    def next_rodada():
        try:
            current_index = rodadas.index(st.session_state.rodada_select)
            if current_index < len(rodadas) - 1:
                st.session_state.rodada_select = rodadas[current_index + 1]
        except ValueError:
            st.session_state.rodada_select = rodadas[0]

    col_prev, col_select, col_next = st.columns([1, 4, 1])
    with col_prev:
        st.button("◀️", use_container_width=True, on_click=prev_rodada, key="prev_rodada_btn_new")
    with col_select:
        rodada_display = f"{st.session_state.rodada_select}ª RODADA"
        st.markdown(f"<div class='rodada-header'>{rodada_display}</div>", unsafe_allow_html=True)
    with col_next:
        st.button("▶️", use_container_width=True, on_click=next_rodada, key="next_rodada_btn_new")

    st.divider()

    selected_rodada = st.session_state.rodada_select
    matches_filtered = all_matches[all_matches['Rodada'] == selected_rodada].sort_values(by='Data')
    
    render_match_list(matches_filtered, team_crests, standings)


def page_statistics(client, competition_id):
    st.header("📈 Estatísticas Detalhadas", anchor=False)

    tab_players, tab_teams = st.tabs(["Estatísticas de Jogadores", "Estatísticas de Times"])

    with tab_players:
        st.subheader("Líderes de Estatísticas (Jogadores)", anchor=False)
        with st.spinner("Carregando estatísticas dos jogadores..."):
            scorers_data = client.get_scorers(competition_id)

        if scorers_data.empty:
            st.warning("Não foi possível carregar as estatísticas dos jogadores.")
        else:
            scorers_data['G+A'] = scorers_data['Gols'] + scorers_data['Assistências']
            cols_order = ['Jogador', 'Time', 'Gols', 'Assistências', 'G+A', 'Pênaltis']
            scorers_data = scorers_data.reindex(columns=cols_order)
            metric_options = {'Gols': 'Gols', 'Assistências': 'Assistências', 'Participações (G+A)': 'G+A', 'Pênaltis': 'Pênaltis'}
            sort_by = st.selectbox("Ordenar por (Jogadores):", options=metric_options.keys(), index=0)
            sorted_data = scorers_data.sort_values(by=metric_options[sort_by], ascending=False).reset_index(drop=True)
            st.dataframe(sorted_data, hide_index=True, use_container_width=True)

    with tab_teams:
        st.subheader("Líderes de Estatísticas (Times)", anchor=False)
        with st.spinner("Carregando estatísticas dos times..."):
            standings_data = client.get_standings(competition_id)

        if standings_data.empty:
            st.warning("Não foi possível carregar as estatísticas dos times.")
        else:
            team_stats = standings_data[['Time', 'J', 'V', 'E', 'D', 'GF', 'GC', 'SG', 'P']]
            team_metric_options = {
                'Pontuação (Classificação)': ('P', False),
                'Melhor Ataque (Gols Marcados)': ('GF', False),
                'Melhor Defesa (Gols Sofridos)': ('GC', True),
                'Pior Ataque (Gols Marcados)': ('GF', True),
                'Pior Defesa (Gols Sofridos)': ('GC', False),
                'Mais Vitórias': ('V', False),
                'Mais Empates': ('E', False),
                'Mais Derrotas': ('D', False)
            }

            team_sort_by = st.selectbox("Ordenar por (Times):", options=team_metric_options.keys(), index=0)

            sort_col, ascending = team_metric_options[team_sort_by]
            sorted_teams = team_stats.sort_values(by=sort_col, ascending=ascending).reset_index(drop=True)
            st.dataframe(sorted_teams, hide_index=True, use_container_width=True)

@st.cache_data
def load_css(file_name="style.css"):
    try:
        with open(file_name, "r", encoding="utf-8") as f:
            css = f.read()
        st.markdown(f'<style>{css}</style>', unsafe_allow_html=True)
    except FileNotFoundError:
        st.error(f"Arquivo CSS '{file_name}' não encontrado.")

def run_app():
    st.set_page_config(page_title="DataFut", layout="wide", page_icon="⚽")

    load_css("style.css")

    st.markdown(f"""
    <div class="main-header">
        <h1>⚽ DataFut</h1>
        <p>Estatísticas completas do Campeonato Brasileiro em tempo real</p>
    </div>
    """, unsafe_allow_html=True)

    try:
        api_key = st.secrets["FOOTBALL_API_KEY"]
    except (FileNotFoundError, KeyError):
        st.error("Chave da API (FOOTBALL_API_KEY) não encontrada.")
        st.info("Por favor, adicione sua chave ao arquivo .streamlit/secrets.toml")
        return

    client = FootballAPIClient(api_key)

    page_key_metrics(client, COMPETITION_ID)

    st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs([
        "Classificação",
        "Análise de Times",
        "Jogos",
        "Estatísticas Detalhadas"
    ])

    with tab1:
        page_standings(client, COMPETITION_ID)
    with tab2:
        page_team_analysis(client, COMPETITION_ID)
    with tab3:
        page_matches(client, COMPETITION_ID)
    with tab4:
        page_statistics(client, COMPETITION_ID)

if __name__ == "__main__":
    run_app()