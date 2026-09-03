import math
from datetime import datetime

import streamlit as st

# ==============================================================================
# CONFIGURAÇÃO
# ==============================================================================

st.set_page_config(
    page_title="Calculadora de índices cardiometabólicos",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Os limites de plausibilidade são configuráveis e devem ser validados pela
# equipe científica antes da publicação, conforme a especificação.
PLAUSIBILITY_LIMITS = {
    "glicemia_mg_dl": (1.0, 1000.0),
    "triglicerideos_mg_dl": (1.0, 3000.0),
    "hdl_mg_dl": (1.0, 300.0),
    "triglicerideos_mmol_l": (0.001, 33.9),
    "hdl_mmol_l": (0.001, 7.75),
}

TYG_CUTOFF = 8.8
IAP_LOW_CUTOFF = 0.10
IAP_HIGH_CUTOFF = 0.24


# ==============================================================================
# IDENTIDADE VISUAL
# ==============================================================================

st.markdown(
    """
    <style>
        :root {
            --bg: #0B0F17;
            --card: #151C28;
            --card-highlight: #12304A;
            --primary: #3B82F6;
            --support: #60A5FA;
            --text: #F4F7FB;
            --muted: #AEB8C5;
            --border: #283343;
            --low: #3F9A82;
            --mid: #D9A441;
            --high: #EF5350;
        }

        .stApp {
            background: var(--bg);
            color: var(--text);
        }

        [data-testid="stHeader"] {
            background: var(--bg);
        }

        .site-title {
            font-size: clamp(2rem, 4vw, 3.4rem);
            line-height: 1.05;
            font-weight: 800;
            letter-spacing: -0.03em;
            margin-bottom: 0.5rem;
            color: var(--text);
        }

        .site-subtitle {
            color: var(--muted);
            font-size: 1.12rem;
            line-height: 1.65;
            max-width: 900px;
        }

        .section-title {
            margin-top: 2rem;
            margin-bottom: 1rem;
        }

        .card {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 1.35rem;
            margin: 0.75rem 0;
        }

        .result-card {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 1.4rem;
            margin: 1rem 0;
        }

        .result-low {
            border-left: 5px solid var(--low);
        }

        .result-mid {
            border-left: 5px solid var(--mid);
        }

        .result-high {
            border-left: 5px solid var(--high);
        }

        .metric-value {
            font-size: 2rem;
            font-weight: 800;
            margin: 0.2rem 0 0.8rem;
        }

        .muted {
            color: var(--muted);
        }

        .warning-box {
            border: 1px solid var(--mid);
            border-radius: 12px;
            padding: 0.9rem 1rem;
            margin: 0.8rem 0;
        }

        .privacy-box {
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 0.9rem 1rem;
            color: var(--muted);
        }

        div.stButton > button,
        div.stFormSubmitButton > button {
            border-radius: 10px;
            font-weight: 700;
        }

        /* Mantém os rótulos visíveis e melhora o foco para teclado. */
        input:focus, textarea:focus, button:focus, [role="radiogroup"]:focus {
            outline: 2px solid var(--support) !important;
            outline-offset: 2px !important;
        }

        @media (max-width: 700px) {
            .site-title {
                font-size: 2rem;
            }

            .site-subtitle {
                font-size: 1rem;
            }
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ==============================================================================
# FUNÇÕES DE VALIDAÇÃO E PARSING
# ==============================================================================

def parse_decimal(value: str, field_name: str) -> float:
    """Converte entrada textual aceitando ponto ou vírgula decimal."""
    if value is None or not value.strip():
        raise ValueError(f"{field_name}: preencha este campo.")

    normalized = value.strip().replace(",", ".")

    try:
        number = float(normalized)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name}: Confira o valor informado.")

    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{field_name}: Confira o valor informado.")

    return number


def validate_plausibility(
    value: float,
    field_name: str,
    limits: tuple[float, float],
) -> bool:
    """
    Verifica plausibilidade sem fazer classificação automática quando o valor
    estiver fora da faixa configurável. Os limites devem ser validados
    cientificamente antes da publicação.
    """
    minimum, maximum = limits
    if value < minimum or value > maximum:
        st.warning(
            f"{field_name}: Confira o valor informado. "
            "O valor está fora da faixa de plausibilidade configurada; "
            "a classificação automática foi bloqueada."
        )
        return False
    return True


# ==============================================================================
# MÓDULO DE CÁLCULO
# ==============================================================================

class CardioEngine:
    """Implementa as fórmulas e critérios definidos na especificação."""

    @staticmethod
    def calcular_tyg(glicemia: float, triglicerideos: float) -> dict:
        """
        TyG = ln[(TG mg/dL × glicemia mg/dL) / 2]
        """
        if glicemia <= 0 or triglicerideos <= 0:
            raise ValueError("Os valores informados devem ser maiores que zero.")

        valor = math.log((triglicerideos * glicemia) / 2.0)

        if valor < TYG_CUTOFF:
            classificacao = "Abaixo do ponto de corte adotado"
            classe_visual = "result-low"
            simbolo = "✓"
            interpretacao = (
                "O resultado encontra-se abaixo do ponto de corte adotado "
                "nesta ferramenta. O TyG é um marcador indireto associado "
                "à resistência à insulina e deve ser interpretado em conjunto "
                "com outros dados clínicos e laboratoriais."
            )
        else:
            classificacao = "Igual ou superior ao ponto de corte adotado"
            classe_visual = "result-high"
            simbolo = "!"
            interpretacao = (
                "O resultado encontra-se igual ou superior ao ponto de corte "
                "adotado nesta ferramenta. O TyG é um marcador indireto associado "
                "à resistência à insulina e deve ser interpretado em conjunto "
                "com outros dados clínicos e laboratoriais."
            )

        return {
            "indice": "TyG",
            "valor": valor,
            "classificacao": classificacao,
            "classe_visual": classe_visual,
            "simbolo": simbolo,
            "referencia": "Ponto de corte adotado: 8,8.",
            "interpretacao": interpretacao,
            "calculo": (
                f"ln[({triglicerideos:g} × {glicemia:g}) / 2] = "
                f"{valor:.12f}"
            ),
        }

    @staticmethod
    def calcular_iap(
        triglicerideos: float,
        hdl: float,
        unidade: str,
    ) -> dict:
        """
        IAP = log10[TG (mmol/L) / HDL-C (mmol/L)].
        Em mg/dL:
          TG mmol/L = TG / 88,57
          HDL mmol/L = HDL / 38,67
        """
        if triglicerideos <= 0 or hdl <= 0:
            raise ValueError("Os valores informados devem ser maiores que zero.")

        if unidade == "mg/dL":
            tg_mmol = triglicerideos / 88.57
            hdl_mmol = hdl / 38.67
            conversao = (
                f"TG: {triglicerideos:g} / 88,57 = {tg_mmol:.12f} mmol/L; "
                f"HDL: {hdl:g} / 38,67 = {hdl_mmol:.12f} mmol/L"
            )
        elif unidade == "mmol/L":
            tg_mmol = triglicerideos
            hdl_mmol = hdl
            conversao = "Valores já informados em mmol/L; não foi necessária conversão."
        else:
            raise ValueError("Unidade inválida.")

        valor = math.log10(tg_mmol / hdl_mmol)

        if valor < IAP_LOW_CUTOFF:
            classificacao = "Baixo risco"
            classe_visual = "result-low"
            simbolo = "✓"
            interpretacao = (
                "A classificação do índice encontra-se na faixa de baixo risco "
                "definida nesta ferramenta."
            )
        elif valor <= IAP_HIGH_CUTOFF:
            classificacao = "Risco intermediário"
            classe_visual = "result-mid"
            simbolo = "!"
            interpretacao = (
                "A classificação do índice encontra-se na faixa de risco "
                "intermediário definida nesta ferramenta."
            )
        else:
            classificacao = "Alto risco"
            classe_visual = "result-high"
            simbolo = "!"
            interpretacao = (
                "A classificação do índice encontra-se na faixa de alto risco "
                "definida nesta ferramenta."
            )

        return {
            "indice": "IAP",
            "valor": valor,
            "classificacao": classificacao,
            "classe_visual": classe_visual,
            "simbolo": simbolo,
            "referencia": (
                "Baixo: < 0,10 | Intermediário: 0,10 a 0,24 | "
                "Alto: > 0,24."
            ),
            "interpretacao": interpretacao,
            "calculo": (
                f"log10({tg_mmol:.12f} / {hdl_mmol:.12f}) = "
                f"{valor:.12f}"
            ),
            "conversao": conversao,
        }

# ==============================================================================
# COMPONENTES DE INTERFACE
# ==============================================================================

def render_resultado(resultado: dict) -> None:
    """Renderiza um resultado com classificação, referência e cálculo."""
    st.markdown(
        f"""
        <div class="result-card {resultado['classe_visual']}">
            <div class="muted">{resultado['indice']}</div>
            <div class="metric-value">{resultado['valor']:.3f}</div>
            <div><strong>{resultado['simbolo']} Classificação do índice:</strong>
            {resultado['classificacao']}</div>
            <p><strong>Referência adotada:</strong> {resultado['referencia']}</p>
            <p>{resultado['interpretacao']}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("Ver como foi calculado"):
        st.write(f"**Cálculo:** {resultado['calculo']}")
        if "conversao" in resultado:
            st.write(f"**Conversão:** {resultado['conversao']}")


def render_aviso_uso() -> None:
    st.info(
        "Os resultados apresentados têm finalidade informativa e educacional, "
        "não estabelecem diagnóstico e não substituem a avaliação de um "
        "profissional de saúde."
    )


def render_campo_decimal(
    label: str,
    key: str,
    exemplo: str = "95",
    unidade: str = "mg/dL",
) -> str:
    st.markdown(f"**{label}**")
    st.caption(f"Unidade: {unidade} · Ex.: {exemplo}")
    return st.text_input(
        label,
        key=key,
        label_visibility="collapsed",
        placeholder=f"Ex.: {exemplo}",
    )


def calcular_completo() -> None:
    """Calcula TyG e IAP simultaneamente após validar os três campos."""
    glicemia_txt = st.session_state.get("glicemia_completa", "")
    tg_txt = st.session_state.get("tg_completo", "")
    hdl_txt = st.session_state.get("hdl_completo", "")

    try:
        glicemia = parse_decimal(glicemia_txt, "Glicemia de jejum")
        tg = parse_decimal(tg_txt, "Triglicerídeos")
        hdl = parse_decimal(hdl_txt, "HDL-colesterol")

        plausiveis = all(
            [
                validate_plausibility(
                    glicemia,
                    "Glicemia de jejum",
                    PLAUSIBILITY_LIMITS["glicemia_mg_dl"],
                ),
                validate_plausibility(
                    tg,
                    "Triglicerídeos",
                    PLAUSIBILITY_LIMITS["triglicerideos_mg_dl"],
                ),
                validate_plausibility(
                    hdl,
                    "HDL-colesterol",
                    PLAUSIBILITY_LIMITS["hdl_mg_dl"],
                ),
            ]
        )

        if not plausiveis:
            st.error(
                "A classificação automática foi bloqueada porque há valor(es) "
                "fora da faixa de plausibilidade configurada."
            )
            return

        tyg = CardioEngine.calcular_tyg(glicemia, tg)
        iap = CardioEngine.calcular_iap(tg, hdl, "mg/dL")

        st.session_state["resultado_completo"] = {
            "glicemia": glicemia,
            "tg": tg,
            "hdl": hdl,
            "tyg": tyg,
            "iap": iap,
        }
    except ValueError as exc:
        st.error(str(exc))


def limpar_campos_completos() -> None:
    for key in ["glicemia_completa", "tg_completo", "hdl_completo"]:
        st.session_state[key] = ""
    st.session_state.pop("resultado_completo", None)


# Pegar opções selecionadas

main_options = ["Início", "Calculadora", "Sobre os índices", "Referências", "Sobre o projeto"]
selected_index = 0

for option in main_options:
    current_is_selected = st.session_state.get(option, False)
    if current_is_selected:
        menu = option
        selected_index = main_options.index(option)
    st.session_state[option] = False


# ==============================================================================
# CABEÇALHO E NAVEGAÇÃO
# ==============================================================================

st.markdown(
    '<div class="site-title">Calculadora de índices cardiometabólicos</div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="site-subtitle">Ferramenta informativa e educacional para '
    "cálculo e interpretação dos índices TyG e IAP.</div>",
    unsafe_allow_html=True,
)

menu = st.radio(
    label="Navegação",
    options = main_options,
    index = selected_index,
    horizontal=True,
    label_visibility="collapsed",
)

# ==============================================================================
# INÍCIO
# ==============================================================================

if menu == "Início":
    st.markdown("## Calcule e interprete os índices cardiometabólicos")
    st.write(
        "Calcule e interprete os índices TyG e IAP a partir de resultados "
        "laboratoriais, utilizando fórmulas e critérios de interpretação "
        "descritos na literatura científica."
    )

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            """
            <div class="card">
                <h3>Análise completa</h3>
                <p>Informe glicemia, triglicerídeos e HDL-colesterol para
                calcular os índices TyG e IAP em uma única análise.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Fazer análise completa", key="home_completa", type="primary"):
            st.session_state["Calculadora"] = True
            st.rerun()

    with col2:
        st.markdown(
            """
            <div class="card">
                <h3>Índices</h3>
                <p>Conheça o índice TyG e o índice aterogênico do plasma (IAP),
                incluindo dados necessários, fórmulas e critérios de interpretação.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Conhecer os índices", key="home_indices"):
            st.session_state["Sobre os índices"] = True
            st.rerun()

    st.markdown("## Opções para realizar o cálculo")

    a, b, c = st.columns(3)
    with a:
        st.markdown("### Análise completa")
        st.write("TyG + IAP em uma única análise.")
        
    with b:
        st.markdown("### Índice TyG")
        st.write(
            "Marcador indireto associado à resistência à insulina, calculado "
            "a partir da glicemia e dos triglicerídeos em jejum."
        )
        
    with c:
        st.markdown("### Índice aterogênico do plasma (IAP)")
        st.write(
            "Índice calculado a partir da relação entre triglicerídeos e "
            "HDL-colesterol."
        )

    st.markdown("## Como funciona")
    st.write("1. Informe os resultados laboratoriais.")
    st.write("2. A ferramenta realiza os cálculos.")
    st.write("3. Consulte o resultado e a interpretação dos índices.")

    st.markdown(
        """
        <div class="privacy-box">
        <strong>Uso responsável:</strong> A Calculadora de índices
        cardiometabólicos é uma ferramenta informativa e educacional. Os
        resultados devem ser interpretados em conjunto com dados clínicos e
        laboratoriais e não substituem avaliação profissional ou diagnóstico médico.
        </div>
        """,
        unsafe_allow_html=True,
    )


# ==============================================================================
# CALCULADORA
# ==============================================================================

elif menu == "Calculadora":
    st.markdown("## Calculadora")

    opcoes = ["Análise completa", "TyG", "IAP"]
    default = st.session_state.pop("navegar_calculadora", "Análise completa")
    if default not in opcoes:
        default = "Análise completa"

    modo = st.radio(
        "Escolha a calculadora",
        opcoes,
        index=opcoes.index(default),
        horizontal=True,
    )

    st.caption("Utilize resultados de exames realizados em jejum.")

    if modo == "Análise completa":
        st.markdown(
            "Informe os resultados laboratoriais para calcular os índices "
            "TyG e IAP simultaneamente."
        )

        with st.form("form_completo"):
            c1, c2, c3 = st.columns(3)
            with c1:
                render_campo_decimal(
                    "Glicemia de jejum",
                    "glicemia_completa",
                    "95",
                    "mg/dL",
                )
            with c2:
                render_campo_decimal(
                    "Triglicerídeos",
                    "tg_completo",
                    "150",
                    "mg/dL",
                )
            with c3:
                render_campo_decimal(
                    "HDL-colesterol",
                    "hdl_completo",
                    "50",
                    "mg/dL",
                )

            calcular = st.form_submit_button(
                "Calcular índices",
                type="primary",
                use_container_width=True,
            )

        if calcular:
            calcular_completo()

        resultado = st.session_state.get("resultado_completo")
        if resultado:
            st.markdown("### Resultado")
            st.write(
                f"**Valores informados:** Glicemia {resultado['glicemia']:g} mg/dL · "
                f"Triglicerídeos {resultado['tg']:g} mg/dL · "
                f"HDL-colesterol {resultado['hdl']:g} mg/dL"
            )

            c1, c2 = st.columns(2)
            with c1:
                render_resultado(resultado["tyg"])
            with c2:
                render_resultado(resultado["iap"])

            render_aviso_uso()
            
    elif modo == "TyG":
        st.markdown("### Calculadora TyG")

        with st.form("form_tyg"):
            c1, c2 = st.columns(2)
            with c1:
                glicemia_txt = render_campo_decimal(
                    "Glicemia de jejum",
                    "glicemia_tyg",
                    "100",
                    "mg/dL",
                )
            with c2:
                tg_txt = render_campo_decimal(
                    "Triglicerídeos",
                    "tg_tyg",
                    "100",
                    "mg/dL",
                )

            calcular = st.form_submit_button(
                "Calcular TyG",
                type="primary",
                use_container_width=True,
            )

        if calcular:
            try:
                glicemia = parse_decimal(glicemia_txt, "Glicemia de jejum")
                tg = parse_decimal(tg_txt, "Triglicerídeos")

                plausiveis = all(
                    [
                        validate_plausibility(
                            glicemia,
                            "Glicemia de jejum",
                            PLAUSIBILITY_LIMITS["glicemia_mg_dl"],
                        ),
                        validate_plausibility(
                            tg,
                            "Triglicerídeos",
                            PLAUSIBILITY_LIMITS["triglicerideos_mg_dl"],
                        ),
                    ]
                )

                if plausiveis:
                    st.session_state["resultado_tyg"] = CardioEngine.calcular_tyg(
                        glicemia, tg
                    )
            except ValueError as exc:
                st.error(str(exc))

        if st.session_state.get("resultado_tyg"):
            render_resultado(st.session_state["resultado_tyg"])
            render_aviso_uso()

    else:
        st.markdown("### Calculadora IAP")

        unidade = st.radio(
            "Seleção da unidade",
            ["mg/dL", "mmol/L"],
            horizontal=True,
            key="unidade_iap",
        )

        with st.form("form_iap"):
            c1, c2 = st.columns(2)
            with c1:
                tg_txt = render_campo_decimal(
                    "Triglicerídeos",
                    "tg_iap",
                    "150" if unidade == "mg/dL" else "1,5",
                    unidade,
                )
            with c2:
                hdl_txt = render_campo_decimal(
                    "HDL-colesterol",
                    "hdl_iap",
                    "50" if unidade == "mg/dL" else "1,0",
                    unidade,
                )

            calcular = st.form_submit_button(
                "Calcular IAP",
                type="primary",
                use_container_width=True,
            )

        if calcular:
            try:
                tg = parse_decimal(tg_txt, "Triglicerídeos")
                hdl = parse_decimal(hdl_txt, "HDL-colesterol")

                if unidade == "mg/dL":
                    limites_tg = PLAUSIBILITY_LIMITS["triglicerideos_mg_dl"]
                    limites_hdl = PLAUSIBILITY_LIMITS["hdl_mg_dl"]
                else:
                    limites_tg = PLAUSIBILITY_LIMITS["triglicerideos_mmol_l"]
                    limites_hdl = PLAUSIBILITY_LIMITS["hdl_mmol_l"]

                plausiveis = all(
                    [
                        validate_plausibility(tg, "Triglicerídeos", limites_tg),
                        validate_plausibility(hdl, "HDL-colesterol", limites_hdl),
                    ]
                )

                if plausiveis:
                    st.session_state["resultado_iap"] = CardioEngine.calcular_iap(
                        tg, hdl, unidade
                    )
            except ValueError as exc:
                st.error(str(exc))

        if st.session_state.get("resultado_iap"):
            render_resultado(st.session_state["resultado_iap"])
            render_aviso_uso()
        


# ==============================================================================
# SOBRE OS ÍNDICES
# ==============================================================================

elif menu == "Sobre os índices":
    st.markdown("## Sobre os índices")
    st.write(
        "Os índices cardiometabólicos combinam resultados laboratoriais para "
        "auxiliar na avaliação de alterações metabólicas. Nesta versão, a "
        "ferramenta disponibiliza o índice TyG e o índice aterogênico do plasma."
    )

    with st.expander("Índice TyG", expanded=False):
        st.markdown("**O que é**")
        st.write(
            "Marcador indireto associado à resistência à insulina, calculado "
            "a partir da glicemia e dos triglicerídeos em jejum."
        )
        st.markdown("**Para que é utilizado**")
        st.write(
            "Auxilia na avaliação de alterações metabólicas no contexto definido "
            "pela literatura e deve ser interpretado com outros dados clínicos "
            "e laboratoriais."
        )
        st.markdown("**Dados necessários**")
        st.write("Glicemia de jejum e triglicerídeos, ambos em mg/dL.")
        st.markdown("**Fórmula**")
        st.latex(r"TyG = \ln\left(\frac{TG\,(mg/dL)\times glicemia\,(mg/dL)}{2}\right)")
        st.markdown("**Critério de interpretação**")
        st.write("Abaixo de 8,8 ou igual/superior a 8,8.")
        st.markdown("**Limitações**")
        st.write(
            "O ponto de corte pode variar conforme a população, o desfecho e "
            "a forma de cálculo."
        )
        st.markdown("**Referência utilizada**")
        st.write(
            "Unger G, Benozzi SF, Perruzza F, Pennacchiotti GL. (2014), "
            "conforme a seleção de referências da especificação."
        )
        st.info("Consultar referências na página Referências.")

    with st.expander("Índice aterogênico do plasma (IAP)", expanded=False):
        st.markdown("**O que é**")
        st.write(
            "Índice calculado a partir da relação entre triglicerídeos e "
            "HDL-colesterol."
        )
        st.markdown("**Para que é utilizado**")
        st.write(
            "Auxilia na avaliação do perfil aterogênico no contexto descrito "
            "na literatura."
        )
        st.markdown("**Dados necessários**")
        st.write(
            "Triglicerídeos e HDL-colesterol. A entrada pode ser em mg/dL ou mmol/L."
        )
        st.markdown("**Fórmula**")
        st.latex(r"IAP = \log_{10}\left(\frac{TG\,(mmol/L)}{HDL\,(mmol/L)}\right)")
        st.markdown("**Critérios de interpretação**")
        st.write(
            "IAP < 0,10: baixo risco; 0,10 a 0,24: risco intermediário; "
            "IAP > 0,24: alto risco."
        )
        st.markdown("**Limitações**")
        st.write(
            "A interpretação deve respeitar o contexto clínico e a literatura "
            "que fundamenta os critérios adotados."
        )
        st.markdown("**Conversão**")
        st.write(
            "Quando os valores são informados em mg/dL, a conversão para mmol/L "
            "é automática: TG ÷ 88,57 e HDL-colesterol ÷ 38,67."
        )
        st.markdown("**Referência utilizada**")
        st.write(
            "Dobiášová M. e Dobiášová M., Frohlich J., conforme a seleção de "
            "referências da especificação."
        )
        st.info("Consultar referências na página Referências.")


# ==============================================================================
# REFERÊNCIAS
# ==============================================================================

elif menu == "Referências":
    st.markdown("## Referências")
    st.write(
        "Publicações utilizadas para fundamentar as fórmulas, conversões e "
        "critérios de interpretação apresentados no site."
    )

    st.markdown("### Índice TyG")

    tyg_refs = [
        (
            "Simental-Mendía LE, Rodríguez-Morán M, Guerrero-Romero F.",
            "The product of fasting glucose and triglycerides as surrogate for "
            "identifying insulin resistance in apparently healthy subjects.",
            "2008",
            "doi.org/10.1089/met.2008.0034",
            "Fórmula/base matemática do TyG.",
        ),
        (
            "Unger G, Benozzi SF, Perruzza F, Pennacchiotti GL.",
            "Triglycerides and glucose index: a useful indicator of insulin resistance.",
            "2014",
            "doi.org/10.1016/j.endonu.2014.06.009",
            "Fórmula adotada e ponto de corte de 8,8.",
        ),
        (
            "Tao LC, Xu JN, Wang TT, Hua F, Li JJ.",
            "Triglyceride-glucose index as a marker in cardiovascular diseases: "
            "landscape and limitations.",
            "2022",
            "doi.org/10.1186/s12933-022-01511-x",
            "Contexto e limitações.",
        ),
        (
            "Lopez-Jaramillo P, Gomez-Arbelaez D, Martinez-Bello D, et al.",
            "Association of the triglyceride glucose index as a measure of insulin "
            "resistance with mortality and cardiovascular disease in populations "
            "from five continents (PURE study).",
            "2023",
            "doi.org/10.1016/S2666-7568(22)00247-1",
            "Contexto de associação e limitações.",
        ),
    ]

    for indice, (autores, titulo, periodico, doi, funcao) in enumerate(tyg_refs):
            with st.expander(titulo):
                st.write(f"**Autores:** {autores}")
                st.write(f"**Periódico/ano:** {periodico}")
                st.write(f"**DOI:** {doi}")
                st.write(f"**Função da referência:** {funcao}")
                st.link_button(
                    "Acessar publicação",
                    f"https://{doi}",
                    key=f"pub_tyg_{indice}",
                )
    st.markdown("### Índice aterogênico do plasma - IAP")

    iap_refs = [
        (
            "Gaggini M, Gorini F, Vassalle C.",
            "Lipids in atherosclerosis: pathophysiology and the role of calculated "
            "lipid indices in assessing cardiovascular risk in patients with hyperlipidemia.",
            "2023",
            "doi.org/10.3390/ijms24010075",
            "Índices lipídicos calculados.",
        ),
        (
            "Dobiášová M, Frohlich J.",
            "The plasma parameter log (TG/HDL-C) as an atherogenic index: correlation "
            "with lipoprotein particle size and esterification rate in apoB-lipoprotein-depleted plasma.",
            "2001",
            "doi.org/10.1016/s0009-9120(01)00263-6",
            "Fundamentação do IAP/AIP.",
        ),
        (
            "Dobiášová M.",
            "AIP-atherogenic index of plasma as a significant predictor of cardiovascular "
            "risk: from research to practice.",
            "2006",
            "pubmed.ncbi.nlm.nih.gov/16526201",
            "Interpretação do IAP/AIP.",
        ),
        (
            "Rabiee Rad M, Ghasempour Dabaghi G, Darouei B, Amani-Beni R.",
            "The association of atherogenic index of plasma with cardiovascular outcomes "
            "in patients with coronary artery disease: a systematic review and meta-analysis.",
            "2024",
            "doi.org/10.1186/s12933-024-02198-y",
            "Síntese de evidências.",
        ),
        (
            "Araújo YB, Almeida ABR, Viana MFM, Meneguz-Moreno RA.",
            "Uso de índices aterogênicos como métodos de avaliação das doenças ateroscleróticas clínicas.",
            "2023",
            "doi.org/10.36660/abc.20230418",
            "Uso de índices aterogênicos.",
        ),
    ]

    for indice, (autores, titulo, periodico, doi, funcao) in enumerate(iap_refs):
        with st.expander(titulo):
            st.write(f"**Autores:** {autores}")
            st.write(f"**Periódico/ano:** {periodico}")
            st.write(f"**DOI:** {doi}")
            st.write(f"**Função da referência:** {funcao}")
            st.link_button(
                "Acessar publicação",
                f"https://{doi}",
                key=f"pub_iap_{indice}",
            )


# ==============================================================================
# SOBRE O PROJETO
# ==============================================================================

else:
    st.markdown("## Sobre o projeto")
    st.write(
        "A Calculadora de índices cardiometabólicos é uma ferramenta digital "
        "desenvolvida para facilitar o cálculo e a interpretação dos índices "
        "TyG e IAP a partir de resultados laboratoriais."
    )
    st.write(
        "A ferramenta foi criada como produto técnico do Programa de Pós-Graduação "
        "em Assistência e Avaliação em Saúde da Universidade Federal de Goiás "
        "(PPGAAS/UFG)."
    )

    st.markdown("### Objetivo")
    st.write(
        "Disponibilizar uma ferramenta simples, acessível e fundamentada na "
        "literatura científica para auxiliar profissionais, pesquisadores e "
        "estudantes na utilização de índices cardiometabólicos."
    )

    st.markdown("### Público")
    st.write(
        "Profissionais da saúde, pesquisadores, docentes e estudantes interessados "
        "na avaliação de marcadores cardiometabólicos."
    )

    st.markdown("### Responsabilidade de uso")
    render_aviso_uso()

    st.markdown("### Créditos")
    st.write("**Desenvolvido por:** Ana Roberta Pereira Sousa.")
    st.write("**Orientação:** Sérgio Henrique Nascente Costa.")
    st.write("**Programa:** PPGAAS/UFG.")
    st.write("**Ano:** 2026.")


# ==============================================================================
# RODAPÉ
# ==============================================================================

st.divider()
st.caption(
    "Calculadora de índices cardiometabólicos — Ferramenta informativa, "
    "educacional e científica para cálculo dos índices TyG e IAP."
)
st.caption(
    "Contato: anaroberta@discente.ufg.br · PPGAAS/UFG - 2026."
)
