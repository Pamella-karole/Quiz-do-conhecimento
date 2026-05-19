import streamlit as st
import pandas as pd
import os
import json
import httpx
from fpdf import FPDF
from datetime import datetime

# Configuração da página
st.set_page_config(page_title="Quiz do Conhecimento", page_icon="🎓", layout="wide")

# --- CREDENCIAIS DO SUPABASE (SISTEMA HÍBRIDO SEGURO) ---
if "SUPABASE_URL" in st.secrets:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
else:
    # Fica limpo aqui para ninguém ver no GitHub
    SUPABASE_URL = "COLE_SUA_URL_AQUI"
    SUPABASE_KEY = "COLE_SUA_CHAVE_ANON_AQUI"

# --- FUNÇÕES DE CONEXÃO COM A NUVEM (SUPABASE - SCHEMA PUBLIC) ---
def supabase_buscar_questoes():
    try:
        base_url = SUPABASE_URL.strip().rstrip('/')
        url = f"{base_url}/rest/v1/questoes?select=*"
        headers = {
            "apikey": SUPABASE_KEY, 
            "Authorization": f"Bearer {SUPABASE_KEY}"
        }
        
        # 30 segundos de timeout para garantir estabilidade na conexão SSL
        response = httpx.get(url, headers=headers, timeout=30.0)
        if response.status_code == 200:
            dados = response.json()
            if dados:
                df = pd.DataFrame(dados)
                df.rename(columns={'nivel': 'nível'}, inplace=True)
                return df
        colunas = ['id', 'disciplina', 'assunto', 'nível', 'enunciado', 'alt_a', 'alt_b', 'alt_c', 'alt_d', 'coluna_correta', 'explicacao', 'img_ref']
        return pd.DataFrame(columns=colunas)
    except Exception as e:
        st.error(f"Erro ao buscar questões na nuvem: {e}")
        return None

def supabase_salvar_questao(nova_questao):
    try:
        base_url = SUPABASE_URL.strip().rstrip('/')
        url = f"{base_url}/rest/v1/questoes"
        headers = {
            "apikey": SUPABASE_KEY, 
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }
        
        dados_envio = nova_questao.copy()
        if 'nível' in dados_envio:
            dados_envio['nivel'] = str(dados_envio.pop('nível'))
            
        for chave in dados_envio:
            dados_envio[chave] = str(dados_envio[chave]).strip()
            
        response = httpx.post(url, headers=headers, json=dados_envio, timeout=30.0)
        
        if response.status_code not in [200, 201]:
            print(f"Erro do Supabase no CMD: {response.status_code} - {response.text}")
            
        return response.status_code in [200, 201]
    except Exception as e:
        print(f"Erro de conexão ao salvar: {e}")
        return False

def supabase_buscar_provas():
    try:
        base_url = SUPABASE_URL.strip().rstrip('/')
        url = f"{base_url}/rest/v1/config_provas?select=*"
        headers = {
            "apikey": SUPABASE_KEY, 
            "Authorization": f"Bearer {SUPABASE_KEY}"
        }
        response = httpx.get(url, headers=headers, timeout=30.0)
        if response.status_code == 200:
            return response.json()
        return []
    except:
        return []

def supabase_salvar_prova(codigo, disc, assu, mix):
    try:
        base_url = SUPABASE_URL.strip().rstrip('/')
        url = f"{base_url}/rest/v1/config_provas"
        headers = {
            "apikey": SUPABASE_KEY, 
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        dados_prova = {
            "codigo_prova": codigo, "disciplina": disc, "assunto": assu,
            "qtd_facil": int(mix['fácil']), "qtd_medio": int(mix['médio']), "qtd_dificil": int(mix['difícil'])
        }
        response = httpx.post(url, headers=headers, json=dados_prova, timeout=30.0)
        return response.status_code in [200, 201]
    except:
        return False

# --- GERADOR DE PDF ---
def gerar_pdf_entrega(nome, codigo, questoes, respostas_aluno, nota_final):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    
    def limpar_texto(txt):
        if not txt: return ""
        t = str(txt)
        t = t.replace('\u2014', ' - ').replace('\u2013', ' - ').replace('\u2015', ' - ')
        t = t.replace('\u201c', '"').replace('\u201d', '"')
        t = t.replace('\u2018', "'").replace('\u2019', "'")
        return t.encode('latin-1', 'replace').decode('latin-1')

    pdf.cell(0, 10, limpar_texto("Comprovante de Entrega de Prova"), ln=True, align='C')
    pdf.ln(5)
    pdf.set_font("Arial", '', 12)
    pdf.cell(0, 8, limpar_texto(f"Aluno: {nome}"), ln=True)
    pdf.cell(0, 8, limpar_texto(f"Código da Prova: {codigo}"), ln=True)
    pdf.cell(0, 8, limpar_texto(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}"), ln=True)
    pdf.ln(4)
    
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, limpar_texto(f"NOTA FINAL: {nota_final:.1f} / 10.0"), ln=True)
    pdf.ln(6)
    
    for i, q in questoes.iterrows():
        pdf.set_font("Arial", 'B', 11)
        pdf.multi_cell(0, 7, limpar_texto(f"Questão {i+1}: {q['enunciado']}"))
        resp = respostas_aluno.get(i, "Não respondida")
        pdf.set_font("Arial", '', 11)
        pdf.multi_cell(0, 7, limpar_texto(f"Sua Resposta: {resp}"))
        pdf.ln(4)
        
    pdf_string = pdf.output(dest='S')
    return pdf_string.encode('latin-1', 'replace')

# --- INICIALIZAÇÃO DO ESTADO ---
if 'pagina' not in st.session_state:
    st.session_state.pagina = "home"
if 'prova_gerada' not in st.session_state:
    st.session_state.update({
        'prova_gerada': False, 'questoes': None, 'entregue': False,
        'nome': "", 'cod': "", 'respostas_aluno': {}
    })

# Baixa as questões em tempo real da nuvem
df = supabase_buscar_questoes()

# --- NAVEGAÇÃO ---

# 1. PÁGINA INICIAL
if st.session_state.pagina == "home":
    st.title("🎓 Sistema de Avaliações SENAI (Nuvem)")
    st.write("---")
    col_aluno, col_prof = st.columns(2)
    with col_aluno:
        st.info("### Área do Aluno")
        if st.button("Sou Aluno 👨‍🎓", use_container_width=True):
            st.session_state.pagina = "aluno"
            st.rerun()
    with col_prof:
        st.warning("### Área do Professor")
        if st.button("Sou Professor 👨‍🏫", use_container_width=True):
            st.session_state.pagina = "professor"
            st.rerun()

# 2. ÁREA DO PROFESSOR (SUPABASE)
elif st.session_state.pagina == "professor":
    if st.button("⬅️ Voltar ao Início"):
        st.session_state.pagina = "home"
        st.rerun()
        
    st.header("⚙️ Painel do Instrutor (Banco de Dados Online)")
    senha = st.text_input("Senha do Professor", type="password")
    
# --- VALIDAÇÃO DE SENHA INTELIGENTE ---
        # Busca "SENHA_PROFESSOR" no cofre do Streamlit. Se não achar (local), usa "senha_teste_local"
        senha_mestra = st.secrets.get("SENHA_PROFESSOR", "senha_teste_local")
        if senha == senha_mestra:
            st.write("---")
            opcao_prof = st.radio("Selecione uma ação:", ["📋 Configurar Nova Prova", "➕ Cadastrar Nova Questão"], horizontal=True)
            st.write("---")

        if opcao_prof == "📋 Configurar Nova Prova":
            if df is not None and not df.empty:
                col1, col2 = st.columns(2)
                with col1:
                    disc = st.selectbox("Disciplina", df['disciplina'].unique())
                    assuntos_lista = list(df[df['disciplina']==disc]['assunto'].unique())
                    assu = st.selectbox("Assunto", ["TODOS"] + assuntos_lista)
                    cod_prova = st.text_input("Código de Acesso (Ex: PROVA10)").upper()
                
                with col2:
                    st.write("**Defina o Mix de Questões:**")
                    q_facil = st.number_input("Fácil", min_value=0, value=1)
                    q_medio = st.number_input("Médio", min_value=0, value=1)
                    q_dificil = st.number_input("Difícil", min_value=0, value=1)
                
                mix_solicitado = {"fácil": q_facil, "médio": q_medio, "difícil": q_dificil}
                erros_banco = []
                
                for nivel, qtd in mix_solicitado.items():
                    if qtd > 0:
                        if assu == "TODOS":
                            disponiveis = len(df[(df['disciplina'] == disc) & (df['nível'] == nivel)])
                        else:
                            disponiveis = len(df[(df['disciplina'] == disc) & (df['assunto'] == assu) & (df['nível'] == nivel)])
                        
                        if disponiveis < qtd:
                            erros_banco.append(f"⚠️ Nível **{nivel.capitalize()}**: você pediu {qtd}, mas só há {disponiveis} na nuvem.")
                
                if erros_banco:
                    st.error("### ❌ Não há questões suficientes no banco!")
                    for erro in erros_banco: st.write(erro)
                    botao_bloqueado = True
                else:
                    botao_bloqueado = False

                if st.button("🚀 Ativar Prova", disabled=botao_bloqueado):
                    if cod_prova:
                        sucesso = supabase_salvar_prova(cod_prova, disc, assu, mix_solicitado)
                        if sucesso:
                            st.success(f"✅ Prova '{cod_prova}' ativada com sucesso no Banco de Dados Online!")
                        else:
                            st.error("Erro ao registrar prova na nuvem. Verifique as configurações.")
                    else: st.error("Insira um código válido.")
            else:
                st.warning("O banco de dados na nuvem está vazio. Cadastre questões primeiro!")

        elif opcao_prof == "➕ Cadastrar Nova Questão":
            st.subheader("Formulário de Cadastro de Questão (Direto para o Supabase)")
            
            c1, c2, c3 = st.columns(3)
            with c1: nova_disc = st.text_input("Disciplina (Ex: Marketing)").strip()
            with c2: novo_assu = st.text_input("Assunto (Ex: Mix de Marketing)").strip()
            with c3: novo_niv = st.selectbox("Nível de Dificuldade", ["fácil", "médio", "difícil"])
                
            novo_enunciado = st.text_area("Enunciado da Questão")
            st.write("**Alternativas de Resposta:**")
            alt_a = st.text_input("Alternativa A")
            alt_b = st.text_input("Alternativa B")
            alt_c = st.text_input("Alternativa C")
            alt_d = st.text_input("Alternativa D")
            
            c4, c5 = st.columns(2)
            with c4:
                gabarito_col = st.selectbox("Qual é a alternativa correta?", 
                                           options=["alt_a", "alt_b", "alt_c", "alt_d"], 
                                           format_func=lambda x: f"Alternativa {x.split('_')[1].upper()}")
            with c5:
                nova_img = st.text_input("Nome da Imagem de referência (Opcional)").strip()
                if not nova_img: nova_img = "nan"
                
            nova_explicacao = st.text_area("Justificativa Pedagógica")
            
            if st.button("💾 Gravar Questão na Nuvem"):
                if nova_disc and novo_assu and novo_enunciado and alt_a and alt_b and alt_c and alt_d and nova_explicacao:
                    
                    nova_questao = {
                        'disciplina': nova_disc, 'assunto': novo_assu, 'nível': novo_niv,
                        'enunciado': novo_enunciado, 'alt_a': alt_a, 'alt_b': alt_b, 'alt_c': alt_c, 'alt_d': alt_d,
                        'coluna_correta': gabarito_col, 'explicacao': nova_explicacao, 'img_ref': nova_img
                    }
                    
                    sucesso = supabase_salvar_questao(nova_questao)
                    if sucesso:
                        st.success("🎉 Questão gravada com sucesso direto no banco de dados na nuvem!")
                        st.rerun()
                    else:
                        st.error("Erro ao salvar. Verifique se o banco de dados está configurado corretamente.")
                else:
                    st.error("❌ Preencha todos os campos obrigatórios.")

# 3. ÁREA DO ALUNO (SUPABASE)
elif st.session_state.pagina == "aluno":
    if not st.session_state.prova_gerada:
        if st.button("⬅️ Voltar"): st.session_state.pagina = "home"; st.rerun()
        st.header("📝 Login Aluno")
        n, c = st.text_input("Nome Completo"), st.text_input("Código da Prova").upper()
        
        if st.button("Iniciar Prova"):
            provas_nuvem = supabase_buscar_provas()
            cfg = next((p for p in provas_nuvem if p['codigo_prova'] == c), None)
            
            if cfg:
                lista_final = []
                mix_cfg = {'fácil': cfg['qtd_facil'], 'médio': cfg['qtd_medio'], 'difícil': cfg['qtd_dificil']}
                
                for nivel, qtd in mix_cfg.items():
                    if qtd > 0:
                        if cfg['assunto'] == "TODOS":
                            sub_df = df[(df['disciplina']==cfg['disciplina']) & (df['nível']==nivel)]
                        else:
                            sub_df = df[(df['disciplina']==cfg['disciplina']) & (df['assunto']==cfg['assunto']) & (df['nível']==nivel)]
                        
                        if not sub_df.empty:
                            n_sorteio = min(len(sub_df), qtd)
                            lista_final.append(sub_df.sample(n=n_sorteio))
                
                if lista_final:
                    st.session_state.questoes = pd.concat(lista_final).sample(frac=1).reset_index(drop=True)
                    st.session_state.prova_gerada = True
                    st.session_state.nome, st.session_state.cod = n, c
                    st.rerun()
                else: st.error("Não há questões suficientes cadastradas para esta prova.")
            else: st.error("Código de prova não encontrado na nuvem.")

    elif st.session_state.prova_gerada and not st.session_state.entregue:
        st.subheader(f"Aluno: {st.session_state.nome} | Código: {st.session_state.cod}")
        resps = {}
        for i, q in st.session_state.questoes.iterrows():
            st.markdown(f"#### Questão {i+1}")
            st.write(q['enunciado'])
            img = str(q['img_ref']).strip()
            if img and img != "nan" and os.path.exists(os.path.join("imagens", img)):
                st.image(os.path.join("imagens", img), width=450)
            
            opcoes = [q['alt_a'], q['alt_b'], q['alt_c'], q['alt_d']]
            resps[i] = st.radio("Escolha uma alternativa:", options=opcoes, key=f"aluno_q_{i}")
            st.divider()
        
        if st.button("📤 Finalizar e Entregar"):
            st.session_state.respostas_aluno = resps
            st.session_state.entregue = True
            st.rerun()

    elif st.session_state.entregue:
        st.header("📊 Revisão da Avaliação")
        st.write(f"Aluno: **{st.session_state.nome}** | Código: **{st.session_state.cod}**")
        st.divider()

        acertos = 0
        for i, q in st.session_state.questoes.iterrows():
            resp_aluno = st.session_state.respostas_aluno[i]
            col_certa = str(q.get('coluna_correta', 'alt_a')).strip().lower()
            texto_correto = q.get(col_certa, "Não encontrada")
            letra_correta = col_certa.split('_')[1].upper() if '_' in col_certa else "A"
            
            st.markdown(f"#### {i+1}. {q['enunciado']}")
            opcoes = {'A': q['alt_a'], 'B': q['alt_b'], 'C': q['alt_c'], 'D': q['alt_d']}
            
            for letra, texto in opcoes.items():
                if texto == resp_aluno and resp_aluno == texto_correto:
                    st.write(f"✅ **{letra}) {texto} (Sua resposta - Correta)**")
                elif texto == resp_aluno and resp_aluno != texto_correto:
                    st.write(f"❌ **{letra}) {texto} (Sua resposta - Incorreta)**")
                elif texto == texto_correto:
                    st.write(f"➡️ *{letra}) {texto} (Resposta correta)*")
                else:
                    st.write(f"{letra}) {texto}")

            explicacao_texto = q.get('explicacao', 'Sem justificativa.')
            if resp_aluno == texto_correto:
                acertos += 1
                st.success(f"**Resposta:** Alternativa ({letra_correta}) - {explicacao_texto}")
            else:
                st.error(f"**Resposta:** Alternativa ({letra_correta}) - {explicacao_texto}")
            st.divider()
            
        nota = (acertos / len(st.session_state.questoes)) * 10
        st.metric("Sua Nota Final", f"{nota:.1f}")
        
        pdf_bytes = gerar_pdf_entrega(st.session_state.nome, st.session_state.cod, st.session_state.questoes, st.session_state.respostas_aluno, nota)
        st.download_button("📥 Baixar Comprovante (PDF)", pdf_bytes, f"Prova_{st.session_state.nome}.pdf", mime='application/pdf')
        
        if st.button("Finalizar Revisão e Sair"):
            st.session_state.update({'prova_gerada': False, 'entregue': False, 'pagina': "home"})
            st.rerun()
