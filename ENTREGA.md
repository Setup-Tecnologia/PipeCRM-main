# Entrega - PipeCRM-main (Flet 0.84+ / Python 3.13)

## main.py
```python
import flet as ft
import pandas as pd
import matplotlib

# Matplotlib em modo headless (Windows + Flet Desktop).
# Importante: definir backend ANTES de importar pyplot.
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from datetime import datetime
#agora vamos converter para onboarding

# --- IMPORTAÃ‡Ã•ES DO SERVIÃ‡O (API) ---
import service
from service import load_sittax, load_user_data, USER_MAP, get_deal_activities, search_users
from utils import MatplotlibChart

# ConfiguraÃ§Ã£o do Matplotlib

# Alias para facilitar
Colors = ft.Colors
Icons = ft.Icons

async def main(page: ft.Page):
    # --- CONFIGURAÃ‡ÃƒO DA PÃGINA ---
    page.title = "Sittax - Portal do Colaborador"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 0
    page.bgcolor = "#121212"
    page.fonts = {
        "Roboto": "https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap"
    }

    # --- COMPATIBILIDADE FLET 0.84+ ---
    # `page.splash`, `page.snack_bar` e `page.open()` nÃƒÂ£o sÃƒÂ£o mais as APIs recomendadas.
    # Helpers simples para manter a lÃƒÂ³gica do app sem crashes.
    loading_open = {"value": False}
    loading_text = ft.Text("Carregando...", color=Colors.WHITE)
    loading_dlg = ft.AlertDialog(
        modal=True,
        bgcolor=Colors.GREY_900,
        content=ft.Container(
            content=ft.Row(
                [ft.ProgressRing(color=Colors.AMBER), loading_text],
                alignment="center",
                vertical_alignment="center",
                spacing=15,
            ),
            padding=20,
        ),
    )

    def safe_show_dialog(dlg: ft.Control) -> bool:
        """
        Flet 0.84+: apenas 1 Dialog pode estar aberto por vez.
        Se jÃ¡ houver um aberto, tentamos fechar e abrir o novo de forma segura.
        """
        try:
            page.show_dialog(dlg)
            return True
        except RuntimeError as ex:
            if "already opened" in str(ex).lower():
                try:
                    page.pop_dialog()
                except Exception:
                    pass
                try:
                    page.show_dialog(dlg)
                    return True
                except Exception:
                    return False
            raise

    def show_loading(message: str = "Carregando..."):
        loading_text.value = message
        if loading_open["value"]:
            page.update()
            return
        loading_open["value"] = safe_show_dialog(loading_dlg)

    def hide_loading():
        if loading_open["value"]:
            try:
                page.pop_dialog()
            except Exception:
                pass
            loading_open["value"] = False

    def show_snack(message: str):
        safe_show_dialog(ft.SnackBar(ft.Text(message)))
    
    # --- 1. INICIALIZAÃ‡ÃƒO DE DADOS ---
    # Carrega a base estÃ¡tica do Sittax uma Ãºnica vez ao iniciar
    print("Inicializando aplicaÃ§Ã£o...")
    df_sittax_global = load_sittax()
    sittax_error = service.LAST_SITTAX_ERROR
    
    # VariÃ¡veis globais de estado
    dados = {
        "df": pd.DataFrame(),
        "colaboradores": list(USER_MAP.keys()), # Carrega lista do mapeamento
        "etapas": []
    }

    # --- 2. TELAS ---

    def tela_login():
        page.clean()
        
        # Estado local
        selected_user_data = {"id": None, "name": None}

        def buscar_click(e):
            term = txt_busca_user.value
            if not term or len(term) < 2:
                dd_users.error_text = "Digite pelo menos 2 caracteres"
                page.update()
                return
            
            dd_users.error_text = None
            btn_busca.disabled = True
            page.update()

            try:
                users = search_users(term)
                if users:
                    dd_users.options = [
                        ft.dropdown.Option(key=str(u['id']), text=f"{u['name']} ({u['email']})") 
                        for u in users
                    ]
                    dd_users.disabled = False
                    dd_users.value = None
                    dd_users.label = "Selecione o usuÃ¡rio encontrado"
                    
                    # Se sÃ³ tiver um, prÃ©-seleciona
                    if len(users) == 1:
                        u = users[0]
                        dd_users.value = str(u['id'])
                        selected_user_data["id"] = u['id']
                        selected_user_data["name"] = u['name']
                        btn_entrar.disabled = False
                else:
                    dd_users.options = []
                    dd_users.disabled = True
                    dd_users.label = "Nenhum usuÃ¡rio encontrado"
                    btn_entrar.disabled = True
            except Exception as ex:
                dd_users.error_text = f"Erro: {ex}"
            
            btn_busca.disabled = False
            page.update()

        def on_user_change(e):
            if dd_users.value:
                uid = int(dd_users.value)
                # Pega o nome do texto da opÃ§Ã£o
                opt_text = next((o.text for o in dd_users.options if o.key == dd_users.value), "UsuÃ¡rio")
                uname = opt_text.split(" (")[0] # Remove o email do display
                
                selected_user_data["id"] = uid
                selected_user_data["name"] = uname
                btn_entrar.disabled = False
            else:
                btn_entrar.disabled = True
            page.update()

        async def entrar(e):
            if selected_user_data["id"]:
                user_name = selected_user_data["name"]
                user_id = selected_user_data["id"]
                
                # Feedback de Carregamento
                btn_entrar.disabled = True
                btn_entrar.text = "Buscando dados na API..."
                show_loading("Buscando dados na API...")

                try:
                    # --- CHAMADA Ã€ API ---
                    # Busca dados frescos do Pipedrive e cruza com Sittax
                    resultado = await service.load_user_data_async(user_name, df_sittax_global, user_id=user_id)
                    
                    if resultado and not resultado['df'].empty:
                        # Atualiza dados globais
                        dados["df"] = resultado['df']
                        dados["etapas"] = resultado['etapas']
                        
                        # Vai para o painel
                        hide_loading()
                        tela_painel(user_name, user_id=user_id)
                    else:
                        hide_loading()
                        btn_entrar.disabled = False
                        btn_entrar.text = "Entrar no Sistema"
                        show_snack("Nenhum dado encontrado para este usuÃ¡rio.")
                        page.update()

                except Exception as ex:
                    print(f"Erro no login: {ex}")
                    hide_loading()
                    btn_entrar.disabled = False
                    btn_entrar.text = "Entrar no Sistema"
                    show_snack(f"Erro de conexÃ£o: {ex}")
                    page.update()

        # Componentes UI
        txt_busca_user = ft.TextField(
            label="Nome do Colaborador", 
            width=260, 
            bgcolor=Colors.GREY_900,
            border_color=Colors.AMBER,
            border_radius=8,
            text_style=ft.TextStyle(color=Colors.WHITE),
            on_submit=buscar_click
        )
        
        btn_busca = ft.IconButton(
            icon=Icons.SEARCH, 
            icon_color=Colors.AMBER, 
            on_click=buscar_click,
            tooltip="Pesquisar na API"
        )

        dd_users = ft.Dropdown(
            width=320,
            label="Pesquise primeiro...",
            options=[],
            disabled=True,
            bgcolor=Colors.GREY_900,
            border_color=Colors.GREY_700,
            border_radius=8,
            text_style=ft.TextStyle(color=Colors.WHITE),
            # Flet 0.84+: Dropdown nÃ£o usa `on_change`; use `on_select`.
        )
        dd_users.on_select = on_user_change

        btn_entrar = ft.ElevatedButton(
            "Entrar no Sistema", 
            on_click=entrar, 
            width=320, height=45,
            disabled=True,
            style=ft.ButtonStyle(
                bgcolor=Colors.AMBER,
                color=Colors.BLACK,
                shape=ft.RoundedRectangleBorder(radius=8)
            )
        )

        card_login = ft.Container(
            content=ft.Column([
                ft.Icon(Icons.SECURITY, size=60, color=Colors.AMBER),
                ft.Text("Portal do Colaborador", size=24, weight="bold", color=Colors.WHITE),
                ft.Text("Busque seu usuÃ¡rio Pipedrive", size=14, color=Colors.GREY_400),
                ft.Container(
                    content=ft.Text(
                        f"Aviso: {sittax_error}",
                        size=12,
                        color=Colors.ORANGE_300,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    bgcolor=Colors.GREY_800,
                    padding=10,
                    border_radius=10,
                    visible=bool(sittax_error),
                ),
                ft.Divider(height=20, color="transparent"),
                ft.Row([txt_busca_user, btn_busca], alignment="center"),
                dd_users,
                btn_entrar
            ], alignment="center", horizontal_alignment="center", spacing=10),
            padding=40, bgcolor=Colors.GREY_900, border_radius=20,
            shadow=ft.BoxShadow(blur_radius=15, color=ft.Colors.with_opacity(0.5, Colors.BLACK)),
            width=400
        )

        page.add(ft.Container(content=card_login, alignment=ft.Alignment.CENTER, expand=True))

    def tela_painel(user, user_id=None):
        page.clean()
        
        # O DataFrame em dados["df"] jÃ¡ Ã© filtrado para o usuÃ¡rio pela API, 
        # mas mantemos o filtro por seguranÃ§a/consistÃªncia
        df_user = dados["df"].copy()

        # --- COMPONENTES AUXILIARES ---
        
        def format_document(v):
            v = str(v)
            if len(v) == 14: # CNPJ
                return f"{v[:2]}.{v[2:5]}.{v[5:8]}/{v[8:12]}-{v[12:]}"
            elif len(v) == 11: # CPF
                return f"{v[:3]}.{v[3:6]}.{v[6:9]}-{v[9:]}"
            return v

        def copiar_cnpj(e):
            val = format_document(e.control.data)
            page.set_clipboard(val)
            show_snack(f"CNPJ/CPF {val} copiado!")
            page.update()

        def copiar_texto(e):
            val = e.control.data
            page.set_clipboard(val)
            show_snack("Copiado para Ã¡rea de transferÃªncia!")
            page.update()

        def criar_linha_copia(label, valor, icon, valor_limpo=None, copiarfunction=copiar_texto):
            texto_copia = valor_limpo if valor_limpo is not None else valor
            return ft.Row([
                ft.Icon(icon, size=18, color=Colors.AMBER),
                ft.Text(f"{label}: ", weight="w600", size=13, color=Colors.GREY_400),
                ft.Text(valor, size=14, weight="bold", color=Colors.WHITE, selectable=True, expand=True),
                ft.IconButton(Icons.COPY, icon_size=16, icon_color=Colors.AMBER_200, 
                            tooltip="Copiar", data=texto_copia, on_click=copiarfunction)
            ], alignment="start", vertical_alignment="center", spacing=5)

        # --- DIALOG DETALHES ---
        def show_details(e):
            cnpj = e.control.data
            try:
                filtro = df_user[df_user['Key'] == str(cnpj)]
                if filtro.empty: return
                row = filtro.iloc[0]
                
                # Dados
                nome = str(row.get('Nome', ''))
                email = str(row.get('OrganizaÃ§Ã£o - E-mail', '') or row.get('Pessoa - E-mail', 'N/A'))
                
                # Telefone
                tel = str(row.get('OrganizaÃ§Ã£o - Telefone', 'N/A'))
                tel_clean = ''.join(filter(str.isdigit, tel))

                status = str(row.get('Status', ''))
                etapa = str(row.get('NegÃ³cio - Etapa', ''))
                dias_ativ = int(row.get('Dias_Sem_Ativ', 0))
                dias_etapa = int(row.get('Dias_Sem_Etapa', 0))
                
                mensalidade = float(row.get('NegÃ³cio - Mensalidade', 0.0))
                usabilidade = str(row.get('Usabilidade', '-'))
                ult_acesso = str(row.get('Ult_Acesso', '-'))

                # Formata o documento para exibiÃ§Ã£o
                cnpj_fmt = format_document(cnpj)

                cor_st = Colors.RED_ACCENT if "Risco" in status else Colors.GREEN
                
                # Container para atividades (carregado dinamicamente)
                col_atividades = ft.Column(spacing=5)
                loading_atividades = ft.ProgressBar(width=100, color=Colors.AMBER, visible=True)
                
                def carregar_atividades_async():
                    try:
                        # Pega o ID do negÃ³cio (precisamos garantir que estÃ¡ no DF)
                        deal_id = row.get('id') # Isso Ã© booleano no DF atual, precisamos do ID real
                        # Como o DF atual nÃ£o tem o ID do deal explÃ­cito na coluna, vamos tentar inferir ou buscar
                        # Melhor abordagem: Adicionar 'id' (deal_id) no PIPE_BASE_COLUMNS em service.py e recarregar
                        # Por enquanto, vamos assumir que precisamos ajustar o service.py primeiro para trazer o ID.
                        pass
                    except:
                        pass

                # Ajuste temporÃ¡rio: Vamos buscar atividades usando o CNPJ/Key para encontrar o deal_id no DF em memÃ³ria se possÃ­vel
                # Mas o ideal Ã© ter o deal_id direto. Vamos usar o que temos.
                # O service.py nÃ£o exporta o deal_id explicitamente no PIPE_BASE_COLUMNS.
                # Vamos adicionar o deal_id no service.py primeiro? NÃ£o, o usuÃ¡rio pediu para ser rÃ¡pido.
                # Vamos assumir que o 'Tem_Atividade_Aberta' Ã© apenas um flag.
                
                # CORREÃ‡ÃƒO: O service.py precisa retornar o ID do Deal para podermos buscar as atividades dele.
                # Vou editar o service.py para incluir 'id' no DataFrame final.
                
                content = ft.Column([
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(Icons.BUSINESS, size=28, color=Colors.AMBER),
                            ft.Text(nome, size=18, weight="bold", expand=True, color=Colors.WHITE)
                        ]),
                        padding=ft.padding.only(bottom=10)
                    ),
                    ft.Divider(color=Colors.GREY_800),
                    criar_linha_copia("CNPJ/CPF", cnpj_fmt, Icons.NUMBERS, valor_limpo=cnpj, copiarfunction=copiar_cnpj),
                    criar_linha_copia("E-mail", email, Icons.EMAIL),
                    criar_linha_copia("Tel", tel, Icons.PHONE, valor_limpo=tel_clean),
                    ft.Divider(color=Colors.GREY_800),
                    ft.Row([
                        ft.Column([
                            ft.Text("Mensalidade", size=12, color=Colors.GREY_400),
                            ft.Text(f"R$ {mensalidade:,.2f}", weight="bold", size=14, color=Colors.AMBER)
                        ]),
                        ft.Column([
                            ft.Text("Usabilidade", size=12, color=Colors.GREY_400),
                            ft.Text(usabilidade, weight="bold", size=14, color=Colors.CYAN_ACCENT)
                        ]),
                        ft.Column([
                            ft.Text("Ãšlt. Acesso", size=12, color=Colors.GREY_400),
                            ft.Text(ult_acesso, weight="bold", size=14, color=Colors.WHITE)
                        ])
                    ], alignment="spaceBetween"),
                    ft.Divider(color=Colors.GREY_800),
                    ft.Row([
                        ft.Column([
                            ft.Text("Status Financeiro", size=12, color=Colors.GREY_400),
                            ft.Container(ft.Text(status, color=Colors.WHITE, size=12, weight="bold"), 
                                       bgcolor=cor_st, padding=6, border_radius=4)
                        ]),
                        ft.Column([
                            ft.Text("Etapa Atual", size=12, color=Colors.GREY_400),
                            ft.Text(etapa, weight="bold", size=12, color=Colors.WHITE)
                        ])
                    ], alignment="spaceBetween"),
                    ft.Divider(color=Colors.GREY_800),
                    ft.Text("MÃ©tricas de Tempo:", weight="bold", size=14, color=Colors.WHITE),
                    ft.Row([
                        ft.Text(f"â±ï¸ {dias_ativ} dias sem atividade", color=Colors.ORANGE_ACCENT if dias_ativ > 15 else Colors.GREY_400),
                        ft.Text(f"ðŸ“… {dias_etapa} dias nesta etapa", color=Colors.GREY_400)
                    ], spacing=20),
                    ft.Divider(color=Colors.GREY_800),
                    ft.Text("Atividades Pendentes:", weight="bold", size=14, color=Colors.WHITE),
                    loading_atividades,
                    col_atividades
                ], spacing=5, scroll=ft.ScrollMode.AUTO)

                dlg = ft.AlertDialog(
                    content=ft.Container(content, width=450, height=500),
                    title=ft.Text("Ficha do Cliente", color=Colors.AMBER),
                    bgcolor=Colors.GREY_900,
                    shape=ft.RoundedRectangleBorder(radius=12)
                )
                page.show_dialog(dlg)


                deal_id = row.get('id') 
                
                if deal_id:
                    def carregar_ativs():
                        # Filtra por deal_id E pelo usuÃ¡rio logado para garantir que sÃ³ veja suas tarefas neste deal
                        owner = USER_MAP.get(user)
                        ats = get_deal_activities(deal_id, owner_id=owner)
                        
                        loading_atividades.visible = False
                        if not ats:
                            col_atividades.controls.append(ft.Text("Nenhuma atividade pendente.", color=Colors.GREY_500, size=12))
                        else:
                            for a in ats:
                                icon = Icons.CALL if a['type'] == 'call' else Icons.EVENT_NOTE
                                col_atividades.controls.append(
                                    ft.Container(
                                        content=ft.Row([
                                            ft.Icon(icon, size=16, color=Colors.AMBER),
                                            ft.Column([
                                                ft.Text(a['subject'], weight="bold", size=13, color=Colors.WHITE),
                                                ft.Text(f"Vence em: {a['due_date']}", size=11, color=Colors.GREY_400),
                                                ft.Text(a['note'][:100] + "..." if len(a['note']) > 100 else a['note'], size=10, color=Colors.GREY_500, italic=True) if a.get('note') else ft.Container()
                                            ], spacing=2, expand=True)
                                        ], alignment="start", vertical_alignment="start"),
                                        padding=10, bgcolor=Colors.GREY_800, border_radius=8,
                                        margin=ft.margin.only(bottom=5)
                                    )
                                )
                        page.update()
                    
                    # Executa em thread separada para nÃ£o travar a UI
                    import threading
                    threading.Thread(target=carregar_ativs, daemon=True).start()
                else:
                    loading_atividades.visible = False
                    col_atividades.controls.append(ft.Text("ID do negÃ³cio nÃ£o encontrado.", color=Colors.RED_400, size=12))
                    page.update()

            except Exception as ex:
                print(f"Erro detalhes: {ex}")

        # --- ABA 1: LISTA & FILTROS ---
        lv_lista = ft.ListView(expand=True, spacing=8, padding=10)
        
        # Filtros Inputs
        txt_busca = ft.TextField(
            label="Buscar (Nome ou CNPJ)", 
            prefix_icon=Icons.SEARCH, 
            expand=True, height=45, 
            text_size=14, bgcolor=Colors.GREY_900, border_radius=8, border_color=Colors.GREY_700
        )
        
        dd_filtro_etapa = ft.Dropdown(
            label="Filtrar por Etapa", 
            options=[ft.dropdown.Option("Todas")] + [ft.dropdown.Option(x) for x in dados["etapas"]], 
            expand=True,
            text_size=13, bgcolor=Colors.GREY_900, border_radius=8, border_color=Colors.GREY_700
        )
        
        txt_dias_filtro = ft.TextField(
            label="Dias >", 
            value="0",
            width=80, height=45, 
            text_size=14, bgcolor=Colors.GREY_900, border_radius=8, border_color=Colors.GREY_700,
            keyboard_type=ft.KeyboardType.NUMBER,
            text_align=ft.TextAlign.CENTER
        )
        
        txt_total = ft.Text("Total: 0", weight="bold", color=Colors.AMBER)

        dd_tipo_data = ft.Dropdown(
            label="Regra de Data",
            options=[
                ft.dropdown.Option("ativ", "Sem Atividade"),
                ft.dropdown.Option("etapa", "Sem Mudar Etapa")
            ],
            value="ativ",
            width=160,
            text_size=13, bgcolor=Colors.GREY_900, border_radius=8, border_color=Colors.GREY_700
        )

        dd_ordenacao = ft.Dropdown(
            label="Ordenar por",
            options=[
                ft.dropdown.Option("nome", "Nome (A-Z)"),
                ft.dropdown.Option("valor_desc", "Maior Valor"),
                ft.dropdown.Option("dias_ativ_desc", "Mais Dias s/ Ativ"),
                ft.dropdown.Option("dias_etapa_desc", "Mais Dias na Etapa")
            ],
            value="nome",
            width=160,
            text_size=13, bgcolor=Colors.GREY_900, border_radius=8, border_color=Colors.GREY_700
        )

        def atualizar_lista(e=None):
            lv_lista.controls.clear()
            res = df_user.copy()
            
            # 1. Filtro Texto
            if txt_busca.value:
                t = txt_busca.value.lower()
                t_clean = ''.join(filter(str.isdigit, t))
                mask = res['Nome'].str.lower().str.contains(t, na=False)
                if t_clean: mask = mask | res['Key'].str.contains(t_clean, na=False)
                res = res[mask]
            
            # 2. Filtro Etapa
            if dd_filtro_etapa.value and dd_filtro_etapa.value != "Todas":
                res = res[res['NegÃ³cio - Etapa'] == dd_filtro_etapa.value]
            
            # 3. Filtro Dias
            try:
                dias_corte = int(txt_dias_filtro.value)
            except:
                dias_corte = 0
            
            if dias_corte > 0:
                coluna_filtro = 'Dias_Sem_Ativ' if dd_tipo_data.value == "ativ" else 'Dias_Sem_Etapa'
                if coluna_filtro in res.columns:
                    res = res[res[coluna_filtro] > dias_corte]

            # 4. OrdenaÃ§Ã£o
            if dd_ordenacao.value == "nome":
                res = res.sort_values(by="Nome", ascending=True)
            elif dd_ordenacao.value == "valor_desc":
                res = res.sort_values(by="NegÃ³cio - Mensalidade", ascending=False)
            elif dd_ordenacao.value == "dias_ativ_desc":
                res = res.sort_values(by="Dias_Sem_Ativ", ascending=False)
            elif dd_ordenacao.value == "dias_etapa_desc":
                res = res.sort_values(by="Dias_Sem_Etapa", ascending=False)

            txt_total.value = f"Total filtrado: {len(res)}"

            if res.empty:
                lv_lista.controls.append(
                    ft.Container(ft.Text("Nenhum resultado com esses filtros.", color=Colors.GREY), alignment=ft.Alignment.CENTER, padding=20)
                )
            else:
                for _, row in res.head(40).iterrows(): # Top 40
                    nm = str(row['Nome'])[:35]
                    k = str(row['Key'])
                    k_fmt = format_document(k)
                    et = str(row.get('NegÃ³cio - Etapa', '-'))
                    
                    uf = str(row.get('OrganizaÃ§Ã£o - Estado de EndereÃ§o', '-'))
                    if uf == 'nan': uf = '-'
                    
                    raw_tel = str(row.get('OrganizaÃ§Ã£o - Telefone', '-'))
                    clean_tel = ''.join(filter(str.isdigit, raw_tel))

                    if dd_tipo_data.value == "ativ":
                        dias_mostra = int(row.get('Dias_Sem_Ativ', 0))
                        txt_dias = f"{dias_mostra}d s/ ativ."
                    else:
                        dias_mostra = int(row.get('Dias_Sem_Etapa', 0))
                        txt_dias = f"{dias_mostra}d na etapa"

                    limite_visual = dias_corte if dias_corte > 0 else 15
                    cor_bola = Colors.RED if dias_mostra > limite_visual else Colors.GREEN
                    
                    # Dados adicionais para o card
                    valor_mensal = float(row.get('NegÃ³cio - Mensalidade', 0.0))
                    status_sittax = str(row.get('Status', ''))
                    cor_status = Colors.GREEN if "Ativo" in status_sittax or "Adimplente" in status_sittax else Colors.RED_ACCENT if "Risco" in status_sittax else Colors.GREY_700

                    card = ft.Container(
                        content=ft.Row([
                            ft.Container(width=10, height=10, border_radius=5, bgcolor=cor_bola, tooltip="Indicador de Atraso"),
                            ft.Column([
                                ft.Text(nm, weight="bold", size=14, color=Colors.WHITE),
                                ft.Row([
                                    ft.Container(
                                        content=ft.Text(uf, size=10, weight="bold", color=Colors.BLACK),
                                        bgcolor=Colors.AMBER, padding=ft.padding.symmetric(horizontal=4, vertical=2), border_radius=4
                                    ),
                                    ft.Container(
                                        content=ft.Text(f"R$ {valor_mensal:,.2f}", size=10, weight="bold", color=Colors.WHITE),
                                        bgcolor=Colors.BLUE_GREY_900, padding=ft.padding.symmetric(horizontal=4, vertical=2), border_radius=4
                                    ),
                                    ft.Container(
                                        content=ft.Text(status_sittax[:15], size=10, color=Colors.WHITE),
                                        bgcolor=cor_status, padding=ft.padding.symmetric(horizontal=4, vertical=2), border_radius=4
                                    ),
                                ], spacing=5, vertical_alignment="center"),
                                ft.Row([
                                    ft.Text(raw_tel, size=12, color=Colors.GREY_400),
                                    ft.IconButton(
                                        Icons.COPY, 
                                        icon_size=14, 
                                        icon_color=Colors.AMBER,
                                        tooltip="Copiar apenas nÃºmeros",
                                        data=clean_tel,
                                        on_click=copiar_texto,
                                        style=ft.ButtonStyle(padding=0)
                                    )
                                ], spacing=2),
                                ft.Text(f"{k_fmt} | {et}", size=11, color=Colors.GREY_500)
                            ], expand=True, spacing=2),
                            ft.Column([
                                ft.Container(
                                    content=ft.Text(txt_dias, size=11, weight="bold", color=Colors.WHITE),
                                    padding=5, bgcolor=Colors.GREY_800, border_radius=5, alignment=ft.Alignment.CENTER
                                ),
                                ft.IconButton(Icons.VISIBILITY, icon_size=20, icon_color=Colors.AMBER, 
                                            data=k, on_click=show_details)
                            ], alignment="center", horizontal_alignment="center")
                        ], alignment="spaceBetween"),
                        padding=ft.padding.symmetric(horizontal=15, vertical=12),
                        bgcolor=Colors.GREY_900, border_radius=10,
                        shadow=ft.BoxShadow(blur_radius=2, color=ft.Colors.with_opacity(0.2, Colors.BLACK))
                    )
                    lv_lista.controls.append(card)
            page.update()

        txt_busca.on_change = atualizar_lista
        # Flet 0.84+: Dropdown nÃ£o usa `on_change`; use `on_select`.
        dd_filtro_etapa.on_select = atualizar_lista
        txt_dias_filtro.on_change = atualizar_lista
        dd_tipo_data.on_select = atualizar_lista
        dd_ordenacao.on_select = atualizar_lista

        # --- ABA 2: GRÃFICOS ---
        def criar_graficos():
            def grafico_card(titulo, fig):
                return ft.Container(
                    content=ft.Column([
                        ft.Text(titulo, size=16, weight="bold", color=Colors.AMBER),
                        ft.Divider(height=10, color="transparent"),
                        ft.Container(content=MatplotlibChart(fig, transparent=True, expand=True), height=300)
                    ]),
                    bgcolor=Colors.GREY_900,
                    border_radius=15,
                    padding=20,
                    shadow=ft.BoxShadow(blur_radius=10, color=ft.Colors.with_opacity(0.3, Colors.BLACK)),
                    margin=ft.margin.only(bottom=15)
                )

            # GrÃ¡fico 1: Barras (Etapas)
            fig1, ax1 = plt.subplots(figsize=(6, 4))
            fig1.patch.set_alpha(0)
            ax1.set_facecolor('#212121')
            
            if 'NegÃ³cio - Etapa' in df_user.columns:
                d_etapa = df_user['NegÃ³cio - Etapa'].value_counts().head(6)
                ax1.barh(d_etapa.index, d_etapa.values, color='#ffca28')
                ax1.set_xlabel('Qtd Clientes', color='white')
                ax1.spines['top'].set_visible(False)
                ax1.spines['right'].set_visible(False)
                ax1.spines['bottom'].set_color('#555555')
                ax1.spines['left'].set_color('#555555')
                ax1.tick_params(axis='x', colors='#cccccc')
                ax1.tick_params(axis='y', colors='#cccccc')
            else:
                ax1.text(0.5, 0.5, 'Sem dados', ha='center', color='white')

            # GrÃ¡fico 2: Pizza (Status Sittax)
            fig2, ax2 = plt.subplots(figsize=(6, 4))
            fig2.patch.set_alpha(0)
            
            if 'Status' in df_user.columns:
                d_status = df_user['Status'].value_counts()
                cores = ['#66bb6a', '#ef5350', '#bdbdbd', '#ffa726'] 
                wedges, texts, autotexts = ax2.pie(
                    d_status.values, labels=d_status.index, autopct='%1.1f%%', 
                    startangle=90, colors=cores, pctdistance=0.85
                )
                centre_circle = plt.Circle((0,0),0.70,fc='#212121')
                fig2.gca().add_artist(centre_circle)
                plt.setp(autotexts, size=9, weight="bold", color="black")
                plt.setp(texts, size=10, color="#cccccc")
            else:
                ax2.text(0.5, 0.5, 'Sem dados', ha='center', color='white')

            # GrÃ¡fico 3: Receita Mensal por Etapa (MRR)
            fig3, ax3 = plt.subplots(figsize=(6, 4))
            fig3.patch.set_alpha(0)
            ax3.set_facecolor('#212121')
            
            if 'NegÃ³cio - Mensalidade' in df_user.columns and 'NegÃ³cio - Etapa' in df_user.columns:
                d_mrr = df_user.groupby('NegÃ³cio - Etapa')['NegÃ³cio - Mensalidade'].sum().sort_values(ascending=True).tail(6)
                ax3.barh(d_mrr.index, d_mrr.values, color='#29b6f6')
                ax3.set_xlabel('Valor Total (R$)', color='white')
                ax3.spines['top'].set_visible(False)
                ax3.spines['right'].set_visible(False)
                ax3.spines['bottom'].set_color('#555555')
                ax3.spines['left'].set_color('#555555')
                ax3.tick_params(axis='x', colors='#cccccc')
                ax3.tick_params(axis='y', colors='#cccccc')
            else:
                ax3.text(0.5, 0.5, 'Sem dados financeiros', ha='center', color='white')

            # GrÃ¡fico 4: MigraÃ§Ãµes no MÃªs Atual
            fig4, ax4 = plt.subplots(figsize=(6, 4))
            fig4.patch.set_alpha(0)
            ax4.set_facecolor('#212121')
            
            migracoes_mes = 0
            if 'Data_Mudanca_Etapa' in df_user.columns:
                # Filtra datas vÃ¡lidas e do mÃªs atual
                hoje = datetime.now()
                mes_atual = hoje.month
                ano_atual = hoje.year
                
                def is_current_month(dt_str):
                    try:
                        if not dt_str: return False
                        dt = datetime.strptime(str(dt_str), "%Y-%m-%d %H:%M:%S")
                        return dt.month == mes_atual and dt.year == ano_atual
                    except:
                        return False
                
                migracoes_mes = df_user['Data_Mudanca_Etapa'].apply(is_current_month).sum()
            
            # Mostra apenas um nÃºmero grande
            ax4.text(0.5, 0.6, str(migracoes_mes), ha='center', va='center', fontsize=40, color='#66bb6a', weight='bold')
            ax4.text(0.5, 0.3, 'MudanÃ§as de Etapa este MÃªs', ha='center', va='center', fontsize=12, color='#cccccc')
            ax4.axis('off')

            return ft.ListView([
                ft.Text("VisÃ£o Geral da Carteira", size=20, weight="bold", color=Colors.WHITE),
                ft.Text("Indicadores de performance e saÃºde", size=12, color=Colors.GREY_400, italic=True),
                ft.Divider(height=20, color="transparent"),
                ft.ResponsiveRow([
                    ft.Column([grafico_card("DistribuiÃ§Ã£o do Funil (Qtd)", fig1)], col={"sm": 12, "md": 6}),
                    ft.Column([grafico_card("SaÃºde Financeira (Status)", fig2)], col={"sm": 12, "md": 6}),
                    ft.Column([grafico_card("Receita Mensal por Etapa (MRR)", fig3)], col={"sm": 12, "md": 6}),
                    ft.Column([grafico_card("Produtividade Recente", fig4)], col={"sm": 12, "md": 6}),
                ])
            ], padding=20, expand=True)

        # --- LAYOUT PRINCIPAL ---
        tabs = ft.Tabs(
            selected_index=0,
            animation_duration=300,
            indicator_color=Colors.AMBER,
            label_color=Colors.AMBER,
            unselected_label_color=Colors.GREY_400,
            tabs=[
                ft.Tab(
                    text="Lista & AÃ§Ãµes",
                    icon=Icons.LIST_ALT_ROUNDED,
                    content=ft.Column([
                        ft.Container(
                            content=ft.Column([
                                ft.Row([txt_busca, dd_filtro_etapa]),
                                ft.Row([
                                    ft.Text("Filtro de Atraso:", weight="bold", color=Colors.GREY_300),
                                    txt_dias_filtro,
                                    ft.Text("dias em", size=12, color=Colors.GREY_400),
                                    dd_tipo_data,
                                    dd_ordenacao,
                                    ft.VerticalDivider(width=20, color=Colors.GREY_800),
                                    txt_total
                                ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=10)
                            ], spacing=10), 
                            bgcolor=Colors.GREY_900, padding=15,
                            border=ft.border.only(bottom=ft.border.BorderSide(1, Colors.GREY_800))
                        ),
                        lv_lista
                    ], expand=True, spacing=0)
                ),
                ft.Tab(
                    text="Dashboard GrÃ¡fico",
                    icon=Icons.INSERT_CHART_OUTLINED,
                    content=criar_graficos()
                ),
            ],
            expand=True,
        )

        async def atualizar_dados(e):
            show_loading("Atualizando dados...")
            
            try:
                # ForÃ§a recarga da API
                resultado = await service.load_user_data_async(user, df_sittax_global, user_id=user_id, force_refresh=True)
                
                if resultado and not resultado['df'].empty:
                    dados["df"] = resultado["df"]
                    dados["etapas"] = resultado["etapas"]
                    
                    hide_loading()
                    show_snack("Dados atualizados com sucesso!")
                    tela_painel(user) # Recarrega a tela
                else:
                    hide_loading()
                    show_snack("NÃ£o foi possÃ­vel atualizar os dados.")
                    page.update()
            except Exception as ex:
                hide_loading()
                print(f"Erro ao atualizar: {ex}")
                show_snack(f"Erro: {ex}")
                page.update()

        # --- EXPORTAÃ‡ÃƒO ---
        def salvar_arquivo(e: ft.FilePickerResultEvent):
            if e.path:
                try:
                    path = e.path
                    if not path.endswith(".xlsx"):
                        path += ".xlsx"
                    df_user.to_excel(path, index=False)
                    show_snack(f"RelatÃ³rio salvo em: {path}")
                    page.update()
                except Exception as ex:
                    show_snack(f"Erro ao salvar: {ex}")
                    page.update()

        file_picker = ft.FilePicker(on_result=salvar_arquivo)
        page.overlay.append(file_picker)

        def exportar_dados(e):
            file_picker.save_file(allowed_extensions=["xlsx"], file_name=f"relatorio_clientes_{datetime.now().strftime('%Y%m%d')}.xlsx")

        header = ft.Container(
            content=ft.Row([
                ft.Column([
                    ft.Text(f"OlÃ¡, {user.split('|')[0].strip()}", size=20, weight="bold", color=Colors.AMBER),
                    ft.Text("Performance e GestÃ£o", size=12, color=Colors.GREY_400)
                ], spacing=2),
                ft.Row([
                    ft.IconButton(Icons.DOWNLOAD, icon_color=Colors.AMBER, tooltip="Exportar Excel", on_click=exportar_dados),
                    ft.IconButton(Icons.REFRESH, icon_color=Colors.AMBER, tooltip="Atualizar Dados", on_click=atualizar_dados),
                    ft.IconButton(Icons.LOGOUT_ROUNDED, icon_color=Colors.AMBER, tooltip="Sair", 
                                # Flet 0.84+: `page.client_storage` removido -> store da sessÃƒÂ£o.
                                on_click=lambda e: [page.session.store.clear(), tela_login()])
                ])
            ], alignment="spaceBetween"),
            bgcolor=Colors.GREY_900, padding=ft.padding.symmetric(horizontal=20, vertical=15),
            shadow=ft.BoxShadow(blur_radius=5, color=ft.Colors.with_opacity(0.5, Colors.BLACK))
        )

        page.add(ft.Column([header, tabs], expand=True, spacing=0))
        atualizar_lista()

    # --- START ---
    # Verifica se jÃ¡ existe sessÃ£o salva, mas forÃ§a recarregar dados da API
    # para garantir que os dados nÃ£o estejam obsoletos.
    # Flet 0.84+: `page.client_storage` removido -> store da sessÃƒÂ£o.
    u = page.session.store.get("user")
    if u and u in dados["colaboradores"]:
        # Opcional: Poderia ir direto pro painel se persistisse o DF, 
        # mas como o DF estÃ¡ em memÃ³ria, melhor ir pro login para recarregar.
        # Para UX melhor, preenchemos o dropdown.
        tela_login()
        # Se quiser auto-login real, precisaria chamar load_user_data aqui e mostrar splash.
    else:
        tela_login()

if __name__ == "__main__":
    # Flet 0.84+: `ft.app()` estÃƒÂ¡ deprecated. Use `ft.run()`.
    ft.run(main)
```

## service.py
```python
import time
import asyncio
import aiohttp
from pathlib import Path
import io
import os

import pandas as pd
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from utils import clean_cnpj, clean_curr

# --- CONFIGURAÃ‡Ã•ES PIPEDRIVE ---
# Token da API do Pipedrive.
# Preferencialmente configure via variÃƒÂ¡vel de ambiente `PIPEDRIVE_API_TOKEN`.
# Fallback (pedido pelo usuÃƒÂ¡rio): token hardcoded para rodar localmente.
API_TOKEN = os.getenv("PIPEDRIVE_API_TOKEN", "09cfb9d8f7250a54cd3da2dc7df187da49bf5022")
BASE_URL = "https://api.pipedrive.com/api/v1" 

# Mapeamento de Custom Fields (Hashes)
FIELD_CNPJ = "a9d521460c01d5201c376d9db43db76ab7199fa0"
FIELD_PHONE = "76c9875a22fc0276dcbd5dcf15c152213876f201"
FIELD_EMAIL = "9d4b0a138ef286d5cce1f8fbd8de01823fd9d3a1"
FIELD_MENSALIDADE = "751bfa06b655238abc28d5b863f036ae8b0454ac"

# Mapeamento de UsuÃ¡rios (Nome no Login -> ID no Pipedrive)
# MANTIDO PARA COMPATIBILIDADE, MAS AGORA USAMOS BUSCA DINÃ‚MICA
USER_MAP = {
    "Andrea Chesini": 24834130,
    "CÃ¡cia da Silva": 24145332,
    "Daniel LÃ¡zaro": 24909370,
    "Fabiane Serenado": 24807543,
    "Felipi Buettgen": 24535755,
    "JoÃ£o LourenÃ§o": 23911956,
    "Michael Crestani": 24887392,
    "Paulo Franco": 23912033,
    "Raissa Denes": 23911978,
}

# Ãšltimo erro ao carregar a base Sittax (Google Sheets).
# A UI pode usar isso para avisar o usuÃ¡rio sem derrubar a inicializaÃ§Ã£o do app.
LAST_SITTAX_ERROR: str | None = None

def search_users(term: str):
    """Busca usuÃ¡rios no Pipedrive pelo nome/email."""
    url = f"{BASE_URL}/users/find"
    params = {
        "term": term,
        "search_by_email": 0,
        "api_token": API_TOKEN
    }
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json().get('data', [])
            if data:
                return [{"id": u["id"], "name": u["name"], "email": u["email"]} for u in data]
    except Exception as e:
        print(f"Erro ao buscar usuÃ¡rios: {e}")
    return []

PIPE_BASE_COLUMNS = [
    "Key",
    "Nome",
    "OrganizaÃ§Ã£o - Nome",
    "Dono",
    "NegÃ³cio - Etapa",
    "NegÃ³cio - Mensalidade",
    "Status",
    "OrganizaÃ§Ã£o - E-mail",
    "OrganizaÃ§Ã£o - Telefone",
    "OrganizaÃ§Ã£o - Estado de EndereÃ§o",
    "Dias_Sem_Ativ",
    "Dias_Sem_Etapa",
    "Tem_Atividade_Aberta",
    "id"
]

CACHE_DIR = Path("storage/temp/pipedrive_cache")
CACHE_TTL_SECONDS = 5 * 60  # 5 minutos
STAGE_CACHE_TTL = 60 * 60  # 1 hora

CACHE_DIR.mkdir(parents=True, exist_ok=True)

_STAGE_CACHE = {"value": None, "ts": 0.0}


def _get_cache_path(owner_id: int) -> Path:
    return CACHE_DIR / f"user_{owner_id}.pkl"


def _load_cached_pipe(owner_id: int):
    cache_path = _get_cache_path(owner_id)
    if not cache_path.exists():
        return None

    age = time.time() - cache_path.stat().st_mtime
    if age > CACHE_TTL_SECONDS:
        return None

    try:
        print(f"Usando cache local para usuÃ¡rio {owner_id} (idade {int(age)}s)...")
        return pd.read_pickle(cache_path)
    except Exception as exc:
        print(f"Falha ao ler cache {cache_path}: {exc}")
        return None


def _save_cached_pipe(owner_id: int, df: pd.DataFrame) -> None:
    cache_path = _get_cache_path(owner_id)
    try:
        df.to_pickle(cache_path)
    except Exception as exc:
        print(f"NÃ£o foi possÃ­vel salvar cache {cache_path}: {exc}")

# --- ASYNC ENGINE ---

async def fetch_page_async(session, endpoint, params, semaphore):
    """Busca uma Ãºnica pÃ¡gina de forma assÃ­ncrona."""
    url = f"{BASE_URL}/{endpoint}"
    
    # Garante que todos os parÃ¢metros sejam strings (aiohttp pode ser chato com ints)
    str_params = {k: str(v) for k, v in params.items()}
    str_params['api_token'] = API_TOKEN
    
    async with semaphore:
        try:
            async with session.get(url, params=str_params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    print(f"Erro {response.status} em {endpoint}: {await response.text()}")
                    return None
        except Exception as e:
            print(f"Exception em {endpoint}: {e}")
            return None

async def fetch_all_data_async(endpoint, params, semaphore=None):
    """Busca todos os dados de um endpoint paginado (Async)."""
    if semaphore is None:
        semaphore = asyncio.Semaphore(20)

    all_data = []
    start = 0
    limit = 500
    params['limit'] = limit
    
    print(f"DEBUG: Iniciando {endpoint} (Async)...")

    async with aiohttp.ClientSession() as session:
        while True:
            params['start'] = start
            data_json = await fetch_page_async(session, endpoint, params, semaphore)
            
            if not data_json:
                break

            items = data_json.get('data')
            if items:
                all_data.extend(items)
                # print(f"DEBUG: {endpoint} page fetched. Items: {len(items)}")
            
            pagination = data_json.get('additional_data', {}).get('pagination', {})
            if not pagination.get('more_items_in_collection'):
                break
            
            start = pagination.get('next_start', start + limit)
    
    print(f"DEBUG: {endpoint} finalizado. Total: {len(all_data)}")
    return all_data

async def get_stages_map_async(force_refresh: bool = False):
    """Mapeia ID da etapa -> Nome da etapa com cache em memÃ³ria (Async)."""
    now_ts = time.time()
    cached_value = _STAGE_CACHE.get("value")
    cache_age = now_ts - _STAGE_CACHE.get("ts", 0.0)
    if not force_refresh and cached_value and cache_age < STAGE_CACHE_TTL:
        return cached_value

    print("Mapeando Etapas (Async)...")
    # Cria semÃ¡foro local para esta operaÃ§Ã£o isolada
    sem = asyncio.Semaphore(20)
    stages = await fetch_all_data_async("stages", {}, sem)
    stage_map = {s['id']: s['name'] for s in stages}
    _STAGE_CACHE["value"] = stage_map
    _STAGE_CACHE["ts"] = now_ts
    return stage_map

def extract_smart_field(item, standard_key, custom_hash):
    """Extrai dados de forma robusta (suporta v1 flat e v2 nested/custom_fields)."""
    # 1. Tenta pelo campo padrÃ£o
    val_std = item.get(standard_key)
    if isinstance(val_std, list) and len(val_std) > 0:
        return val_std[0].get('value', '')
    if isinstance(val_std, str) and val_std.strip():
        return val_std

    # 2. Tenta pelo Hash (Custom Field)
    custom_fields_dict = item.get('custom_fields')
    val_custom = None
    if isinstance(custom_fields_dict, dict):
        val_custom = custom_fields_dict.get(custom_hash)
    else:
        val_custom = item.get(custom_hash)
    
    if val_custom:
        return str(val_custom)
    return ""

async def fetch_with_retry(session, url, params, semaphore, retries=8, backoff_factor=1.8):
    """Executa requisiÃ§Ã£o GET com retry exponencial para Rate Limits (429)."""
    delay = 1.0
    for i in range(retries):
        async with semaphore:
            try:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        return await response.json()
                    elif response.status == 429:
                        print(f"Rate Limit (429) em {url}. Tentativa {i+1}/{retries}. Aguardando {delay:.1f}s...")
                    else:
                        print(f"Erro {response.status} em {url}: {await response.text()}")
                        return None
            except Exception as e:
                print(f"Exception em {url}: {e}")
                return None
        
        # Se chegou aqui, foi 429 ou erro. Aguarda fora do semÃ¡foro para liberar slot.
        await asyncio.sleep(delay)
        delay *= backoff_factor
    
    print(f"Falha apÃ³s {retries} tentativas em {url}")
    return None

async def get_org_details_async(session, org_id, semaphore):
    """Busca detalhes de uma organizaÃ§Ã£o (Async)."""
    if not org_id: return None
    url = f"{BASE_URL}/organizations/{org_id}"
    params = {'api_token': API_TOKEN}
    
    data = await fetch_with_retry(session, url, params, semaphore)
    if data:
        return data.get('data')
    return None

async def get_organizations_map_async(org_ids, semaphore):
    """Busca detalhes de mÃºltiplas organizaÃ§Ãµes em paralelo."""
    unique_ids = list(set([oid for oid in org_ids if oid]))
    print(f"Baixando detalhes de {len(unique_ids)} OrganizaÃ§Ãµes (Async)...")
    
    org_map = {}
    async with aiohttp.ClientSession() as session:
        tasks = [get_org_details_async(session, oid, semaphore) for oid in unique_ids]
        results = await asyncio.gather(*tasks)
        
        for org in results:
            if org:
                org_id = org.get('id')
                # EndereÃ§o
                addr_obj = org.get('address')
                estado = '-'
                if isinstance(addr_obj, dict):
                    estado = addr_obj.get('admin_area_level_1') or '-'
                elif isinstance(org.get('address_admin_area_level_1'), str):
                     estado = org.get('address_admin_area_level_1')

                # ExtraÃ§Ã£o Inteligente
                phone = extract_smart_field(org, 'phone', FIELD_PHONE)
                email = extract_smart_field(org, 'email', FIELD_EMAIL)
                cnpj = extract_smart_field(org, 'dummy_cnpj', FIELD_CNPJ)

                org_map[org_id] = {
                    "name": org.get('name', 'Sem Nome'),
                    "cnpj": cnpj,
                    "phone": phone,
                    "email": email,
                    "estado": estado
                }
    print(f"Mapeamento de OrganizaÃ§Ãµes concluÃ­do. Total: {len(org_map)}")
    return org_map

async def get_pipedrive_data_optimized(owner_id, stage_map):
    """VersÃ£o Async Otimizada do Pipeline de Dados."""
    print("Iniciando download paralelo (Async) de Atividades e NegÃ³cios...")
    
    semaphore = asyncio.Semaphore(5) # Reduzido drasticamente para evitar 429

    # 1. Busca Deals e Activities em paralelo
    task_deals = fetch_all_data_async("deals", {"user_id": owner_id, "status": "open"}, semaphore)
    task_activities = fetch_all_data_async("activities", {"user_id": owner_id, "done": 0}, semaphore)
    
    deals, activities = await asyncio.gather(task_deals, task_activities)
    
    # 2. Processa IDs
    deals_with_open_activity = set(a['deal_id'] for a in activities if a.get('deal_id'))
    
    org_ids = []
    for deal in deals:
        org_data_raw = deal.get('org_id')
        if org_data_raw:
            oid = org_data_raw.get('value') if isinstance(org_data_raw, dict) else org_data_raw
            org_ids.append(oid)
            
    # 3. Busca OrganizaÃ§Ãµes em paralelo
    org_map = await get_organizations_map_async(org_ids, semaphore)
    
    processed_data = []
    print(f"Processando {len(deals)} negÃ³cios...")

    for deal in deals:
        deal_id = deal.get('id')
        stage_id = deal.get('stage_id')
        stage_name = stage_map.get(stage_id, f"Etapa {stage_id}")

        # Link com OrganizaÃ§Ã£o
        org_data_raw = deal.get('org_id') 
        org_id = org_data_raw.get('value') if isinstance(org_data_raw, dict) else org_data_raw
        
        # Garante que org_id seja int se possÃ­vel, para bater com o mapa
        try:
            if org_id is not None:
                org_id = int(org_id)
        except:
            pass

        org_details = org_map.get(org_id, {"name": "", "cnpj": "", "phone": "", "email": "", "estado": "-"})
        
        # Valor (Mensalidade via Custom Field)
        raw_val = deal.get(FIELD_MENSALIDADE)
        if raw_val is None and isinstance(deal.get('custom_fields'), dict):
             raw_val = deal['custom_fields'].get(FIELD_MENSALIDADE)
        
        try:
            val_float = float(raw_val) if raw_val is not None else 0.0
        except (ValueError, TypeError):
            val_float = 0.0

        # --- LÃ“GICA DE DATAS (PRESERVADA) ---
        now = datetime.now()
        update_time = deal.get('update_time')
        stage_change_time = deal.get('stage_change_time')
        add_time = deal.get('add_time')
        
        dias_etapa = 0
        # Se nÃ£o tiver stage_change_time (nunca mudou), usa a data de criaÃ§Ã£o (add_time)
        ref_date_str = stage_change_time if stage_change_time else add_time
        
        if ref_date_str:
            try:
                dt_etapa = datetime.strptime(ref_date_str, "%Y-%m-%d %H:%M:%S")
                dias_etapa = (now - dt_etapa).days
            except: pass

        dias_sem_ativ = 0
        last_act_date = deal.get('last_activity_date')
        if last_act_date:
            try:
                dt_ativ = datetime.strptime(last_act_date, "%Y-%m-%d")
                dias_sem_ativ = (now - dt_ativ).days
            except: pass
        elif update_time:
            try:
                dt_upd = datetime.strptime(update_time, "%Y-%m-%d %H:%M:%S")
                dias_sem_ativ = (now - dt_upd).days
            except: pass
        # ------------------------------------

        processed_data.append({
            "Key": clean_cnpj(org_details['cnpj']),
            "Nome": deal.get('title'),
            "OrganizaÃ§Ã£o - Nome": org_details.get('name', ''),
            "Dono": deal.get('owner_name', 'Desconhecido'),
            "NegÃ³cio - Etapa": stage_name,
            "NegÃ³cio - Mensalidade": val_float,
            "Status": "Open",
            "OrganizaÃ§Ã£o - E-mail": org_details['email'],
            "OrganizaÃ§Ã£o - Telefone": org_details['phone'],
            "OrganizaÃ§Ã£o - Estado de EndereÃ§o": org_details['estado'],
            "Dias_Sem_Ativ": dias_sem_ativ,
            "Dias_Sem_Etapa": dias_etapa,
            "Data_Mudanca_Etapa": stage_change_time, # Nova coluna para grÃ¡ficos
            "Tem_Atividade_Aberta": deal_id in deals_with_open_activity,
            "id": deal_id
        })

    return pd.DataFrame(processed_data)

def load_sittax():
    """Carrega apenas o Google Sheets (Base estÃ¡tica)"""
    global LAST_SITTAX_ERROR
    sheet_id = "15ziIGCcdLdfvzkovyvgWjzW0-yRCYcHThYFhDYLXQvE"
    gid_sittax = "607928795"
    url_sittax = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid_sittax}"

    # Reseta o erro anterior para a UI poder refletir o estado atual.
    LAST_SITTAX_ERROR = None

    print("Carregando Sittax (Base)...")
    try:
        # Baixa manualmente para:
        # - aplicar timeout e nÃ£o travar o app na inicializaÃ§Ã£o
        # - detectar HTTP 410 (endpoint removido) e nÃ£o quebrar a UI
        r = requests.get(url_sittax, timeout=15)
        if r.status_code == 410:
            # MantÃ©m a aplicaÃ§Ã£o funcionando mesmo sem a base Sittax.
            # A UI pode ler `service.LAST_SITTAX_ERROR` para avisar o usuÃ¡rio.
            LAST_SITTAX_ERROR = (
                "Base Sittax indisponÃ­vel (HTTP 410: Gone). "
                "A planilha/endpoint pode ter sido removida, movida ou alterada."
            )
            print(f"Erro Sittax: {LAST_SITTAX_ERROR}")
            return pd.DataFrame()
        r.raise_for_status()
        df_sittax = pd.read_csv(io.StringIO(r.text), dtype=str)
    except Exception as e:
        LAST_SITTAX_ERROR = str(e)
        print(f"Erro Sittax: {e}")
        return pd.DataFrame()

    if not df_sittax.empty:
        df_sittax.columns = df_sittax.columns.str.strip()
        col_cnpj = next((c for c in df_sittax.columns if "CNPJ" in c.upper()), "CPF/CNPJ")
        if col_cnpj in df_sittax.columns:
            df_sittax['Key'] = df_sittax[col_cnpj].apply(clean_cnpj)
        
        col_vlr = 'Vlr. Mensalidade'
        if col_vlr in df_sittax.columns:
            df_sittax['Vlr_Sittax'] = df_sittax[col_vlr].apply(clean_curr)
        else: 
            df_sittax['Vlr_Sittax'] = 0.0
        
        col_status = next((c for c in df_sittax.columns if 'status' in c.lower()), None)
        df_sittax['Status_Sittax'] = df_sittax[col_status] if col_status else 'Desconhecido'

        col_usa = next((c for c in df_sittax.columns if 'usabilidade' in c.lower() or ('mÃ©dia' in c.lower() and '%' in c)), None)
        df_sittax['Usabilidade_Sittax'] = df_sittax[col_usa] if col_usa else '-'

        col_uf = next((c for c in df_sittax.columns if c.upper() == 'UF'), None)
        df_sittax['UF_Sittax'] = df_sittax[col_uf] if col_uf else '-'

        col_acesso = next((c for c in df_sittax.columns if 'acesso' in c.lower() and 'Ãºlt' in c.lower()), None)
        df_sittax['Ult_Acesso_Sittax'] = df_sittax[col_acesso] if col_acesso else '-'

        cols_to_keep = ['Key', 'Status_Sittax', 'Vlr_Sittax', 'Usabilidade_Sittax', 'UF_Sittax', 'Ult_Acesso_Sittax']
        cols = [c for c in cols_to_keep if c in df_sittax.columns]
        df_sittax = df_sittax[cols]
        df_sittax = df_sittax[df_sittax['Key'] != ""]
    
    return df_sittax

def load_user_data(user_name, df_sittax, user_id=None, force_refresh: bool = False):
    """
    Wrapper sÃ­ncrono.

    Importante (Flet 0.84+): dentro de handlers do Flet jÃ¡ existe um event loop em execuÃ§Ã£o.
    Nesse cenÃ¡rio, `load_user_data()` nÃ£o pode usar `run_until_complete()` (gera
    "This event loop is already running").

    - Dentro do app: use `await load_user_data_async(...)`
    - Fora do app: pode chamar `load_user_data(...)`
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(load_user_data_async(user_name, df_sittax, user_id=user_id, force_refresh=force_refresh))

    raise RuntimeError("Use `await load_user_data_async(...)` dentro do app Flet.")


async def load_user_data_async(user_name, df_sittax, user_id=None, force_refresh: bool = False):
    """Carrega Pipedrive do usuÃ¡rio selecionado, com cache local e cruzamento Sittax (async, compatÃ­vel com Flet)."""
    if user_id is None:
        user_id = USER_MAP.get(user_name)

    if not user_id:
        return None

    df_pipe = None if force_refresh else _load_cached_pipe(user_id)
    if df_pipe is None:
        print(f"Iniciando carga Pipedrive para {user_name}...")
        stage_map = await get_stages_map_async()
        df_pipe = await get_pipedrive_data_optimized(user_id, stage_map)

        if df_pipe.empty:
            df_pipe = pd.DataFrame(columns=PIPE_BASE_COLUMNS)
        df_pipe = df_pipe.copy()
        df_pipe["Dono"] = user_name
        _save_cached_pipe(user_id, df_pipe)
    else:
        df_pipe = df_pipe.copy()
        df_pipe["Dono"] = user_name

    # --- MERGE ---
    if "Key" not in df_pipe.columns:
        df_pipe["Key"] = ""
    df_pipe["Key"] = df_pipe["Key"].astype(str)

    if not df_sittax.empty:
        df_sittax["Key"] = df_sittax["Key"].astype(str)
        df_final = pd.merge(df_pipe, df_sittax, on="Key", how="left")
    else:
        df_final = df_pipe.copy()

    # ConsolidaÃ§Ã£o
    default_len = len(df_final)
    df_final["Status"] = df_final.get("Status_Sittax", pd.Series(["NÃ£o Integrado"] * default_len)).fillna("NÃ£o Integrado")
    df_final["Usabilidade"] = df_final.get("Usabilidade_Sittax", pd.Series(["-"] * default_len)).fillna("-")
    df_final["UF"] = df_final.get("UF_Sittax", pd.Series(["-"] * default_len)).fillna(
        df_final.get("OrganizaÃ§Ã£o - Estado de EndereÃ§o", "-")
    )
    df_final["Ult_Acesso"] = df_final.get("Ult_Acesso_Sittax", pd.Series(["-"] * default_len)).fillna("-")
    df_final["Vlr_Sittax"] = df_final.get("Vlr_Sittax", pd.Series([0.0] * default_len)).fillna(0.0)

    etapas = []
    if "NegÃ³cio - Etapa" in df_final.columns:
        etapas = sorted(x for x in df_final["NegÃ³cio - Etapa"].dropna().unique())

    return {"df": df_final, "colaboradores": list(USER_MAP.keys()), "etapas": etapas}

def get_deal_activities(deal_id, owner_id=None):
    """Busca atividades pendentes de um negÃ³cio especÃ­fico (API v1)"""
    try:
        # Endpoint CORRETO para atividades de um deal especÃ­fico
        url = f"https://api.pipedrive.com/api/v1/deals/{deal_id}/activities"
        params = {
            "api_token": API_TOKEN,
            "done": 0, # 0 = nÃ£o feito
            "exclude": "", # Garante que nÃ£o exclua nada por padrÃ£o
            "limit": 50
        }
        
        # Timeout curto para nÃ£o travar a UI
        r = requests.get(url, params=params, timeout=5)
        if r.status_code == 200:
            data = r.json().get('data', [])
            if data is None: return [] # API pode retornar None se vazio
            
            # Se owner_id for fornecido, filtra localmente os resultados
            if owner_id:
                # user_id no retorno da API geralmente Ã© int
                data = [a for a in data if str(a.get('user_id')) == str(owner_id)]

            return [{
                "subject": a.get("subject", "Sem tÃ­tulo"),
                "due_date": a.get("due_date", "-"),
                "type": a.get("type", "call"),
                "note": a.get("note", "")
            } for a in data]
    except Exception as e:
        print(f"Erro ao buscar atividades do deal {deal_id}: {e}")
    return []
```

## views/dashboard.py
```python
import flet as ft
from utils import format_document, criar_linha_copia, copiar_texto
from views.charts import criar_graficos_view
from views.details import show_details_dialog

def tela_painel(page: ft.Page, user, dados, on_logout):
    page.clean()
    
    # Filtra dados do usuÃ¡rio
    df_user = dados["df"][dados["df"]['Dono'] == user].copy()

    # --- ABA 1: LISTA & FILTROS ---
    lv_lista = ft.ListView(expand=True, spacing=8, padding=10)
    
    # Filtros Inputs
    txt_busca = ft.TextField(
        label="Buscar (Nome ou CNPJ)", 
        prefix_icon=ft.Icons.SEARCH, 
        expand=True, height=45, 
        text_size=14, bgcolor=ft.Colors.GREY_900, border_radius=8, border_color=ft.Colors.GREY_700
    )
    
    dd_filtro_etapa = ft.Dropdown(
        label="Filtrar por Etapa", 
        options=[ft.dropdown.Option("Todas")] + [ft.dropdown.Option(x) for x in dados["etapas"]], 
        expand=True,
        text_size=13, bgcolor=ft.Colors.GREY_900, border_radius=8, border_color=ft.Colors.GREY_700
    )
    
    # NOVO: Filtro de Dias FlexÃ­vel
    txt_dias_filtro = ft.TextField(
        label="Dias >", 
        value="0",
        width=80, height=45, 
        text_size=14, bgcolor=ft.Colors.GREY_900, border_radius=8, border_color=ft.Colors.GREY_700,
        keyboard_type=ft.KeyboardType.NUMBER,
        text_align=ft.TextAlign.CENTER
    )
    
    # NOVO: Texto para mostrar o total
    txt_total = ft.Text("Total: 0", weight="bold", color=ft.Colors.AMBER)

    dd_tipo_data = ft.Dropdown(
        label="Regra de Data",
        options=[
            ft.dropdown.Option("ativ", "Sem Atividade"),
            ft.dropdown.Option("etapa", "Sem Mudar Etapa")
        ],
        value="ativ",
        width=160,
        text_size=13, bgcolor=ft.Colors.GREY_900, border_radius=8, border_color=ft.Colors.GREY_700
    )

    def atualizar_lista(e=None):
        lv_lista.controls.clear()
        res = df_user.copy()
        
        # 1. Filtro Texto
        if txt_busca.value:
            t = txt_busca.value.lower()
            t_clean = ''.join(filter(str.isdigit, t))
            mask = res['Nome'].str.lower().str.contains(t, na=False)
            if t_clean: mask = mask | res['Key'].str.contains(t_clean, na=False)
            res = res[mask]
        
        # 2. Filtro Etapa
        if dd_filtro_etapa.value and dd_filtro_etapa.value != "Todas":
            res = res[res['NegÃ³cio - Etapa'] == dd_filtro_etapa.value]
        
        # 3. Filtro Dias (FlexÃ­vel)
        try:
            dias_corte = int(txt_dias_filtro.value)
        except:
            dias_corte = 0
        
        if dias_corte > 0:
            coluna_filtro = 'Dias_Sem_Ativ' if dd_tipo_data.value == "ativ" else 'Dias_Sem_Etapa'
            # Garante que a coluna existe (se nÃ£o existir, assume 0)
            if coluna_filtro in res.columns:
                res = res[res[coluna_filtro] > dias_corte]

        # Atualiza o contador no topo
        txt_total.value = f"Total filtrado: {len(res)}"

        # RenderizaÃ§Ã£o
        if res.empty:
            lv_lista.controls.append(
                ft.Container(ft.Text("Nenhum resultado com esses filtros.", color=ft.Colors.GREY), alignment=ft.Alignment.CENTER, padding=20)
            )
        else:
            for _, row in res.head(40).iterrows(): # Top 40
                nm = str(row['Nome'])[:35]
                k = str(row['Key'])
                k_fmt = format_document(k) # Formata na lista tambÃ©m
                et = str(row.get('NegÃ³cio - Etapa', '-'))
                
                # Novos campos: Estado e Telefone
                uf = str(row.get('OrganizaÃ§Ã£o - Estado de EndereÃ§o', '-'))
                if uf == 'nan': uf = '-'
                
                # LÃ³gica robusta para encontrar telefone na lista
                raw_tel = '-'
                for col_tel in ['Pessoa - Telefone - Celular', 'Pessoa - Telefone', 'OrganizaÃ§Ã£o - Telefone', 'Telefone']:
                    val = row.get(col_tel)
                    if val and str(val) != 'nan' and str(val).strip():
                        raw_tel = str(val)
                        break

                # Limpa telefone para cÃ³pia (apenas nÃºmeros)
                clean_tel = ''.join(filter(str.isdigit, raw_tel))
                
                # Pega os dias baseado na escolha atual para mostrar no card
                if dd_tipo_data.value == "ativ":
                    dias_mostra = int(row.get('Dias_Sem_Ativ', 0))
                    txt_dias = f"{dias_mostra}d s/ ativ."
                else:
                    dias_mostra = int(row.get('Dias_Sem_Etapa', 0))
                    txt_dias = f"{dias_mostra}d na etapa"

                # Cor de alerta se passar do filtro definido (ou 15 padrÃ£o)
                limite_visual = dias_corte if dias_corte > 0 else 15
                cor_bola = ft.Colors.RED if dias_mostra > limite_visual else ft.Colors.GREEN
                
                card = ft.Container(
                    content=ft.Row([
                        ft.Container(width=10, height=10, border_radius=5, bgcolor=cor_bola),
                        ft.Column([
                            ft.Text(nm, weight="bold", size=14, color=ft.Colors.WHITE), # Texto Branco
                            # Linha do meio: UF e Telefone com cÃ³pia
                            ft.Row([
                                ft.Container(
                                    content=ft.Text(uf, size=11, weight="bold", color=ft.Colors.BLACK),
                                    bgcolor=ft.Colors.AMBER, padding=ft.padding.symmetric(horizontal=6, vertical=2), border_radius=4
                                ),
                                ft.Text(raw_tel, size=12, color=ft.Colors.GREY_400),
                                ft.IconButton(
                                    ft.Icons.COPY, 
                                    icon_size=14, 
                                    icon_color=ft.Colors.AMBER, # Icone Amarelo
                                    tooltip="Copiar apenas nÃºmeros",
                                    data=clean_tel, # Passa o numero limpo
                                    on_click=lambda e: copiar_texto(e, page, "Telefone"),
                                    style=ft.ButtonStyle(padding=0)
                                )
                            ], spacing=5, vertical_alignment="center"),
                            ft.Text(f"{k_fmt} | {et}", size=11, color=ft.Colors.GREY_500)
                        ], expand=True, spacing=2),
                        ft.Container(
                            content=ft.Text(txt_dias, size=11, weight="bold", color=ft.Colors.WHITE),
                            padding=5, bgcolor=ft.Colors.GREY_800, border_radius=5
                        ),
                        ft.IconButton(ft.Icons.VISIBILITY, icon_size=20, icon_color=ft.Colors.AMBER, 
                                    data=k, on_click=lambda e: show_details_dialog(page, e.control.data, df_user))
                    ], alignment="spaceBetween"),
                    padding=ft.padding.symmetric(horizontal=15, vertical=12),
                    bgcolor=ft.Colors.GREY_900, border_radius=10, # Card Escuro
                    shadow=ft.BoxShadow(blur_radius=2, color=ft.Colors.with_opacity(0.2, ft.Colors.BLACK))
                )
                lv_lista.controls.append(card)
        page.update()

    # Eventos dos filtros
    txt_busca.on_change = atualizar_lista
    # Flet 0.84+: Dropdown nÃ£o usa `on_change`; use `on_select`.
    dd_filtro_etapa.on_select = atualizar_lista
    txt_dias_filtro.on_change = atualizar_lista
    dd_tipo_data.on_select = atualizar_lista

    # --- LAYOUT PRINCIPAL ---
    tabs = ft.Tabs(
        selected_index=0,
        animation_duration=300,
        indicator_color=ft.Colors.AMBER, # Indicador Amarelo
        label_color=ft.Colors.AMBER,     # Texto Ativo Amarelo
        unselected_label_color=ft.Colors.GREY_400,
        tabs=[
            ft.Tab(
                text="Lista & AÃ§Ãµes",
                icon=ft.Icons.LIST_ALT_ROUNDED,
                content=ft.Column([
                    # Barra de Filtros Fixa
                    ft.Container(
                        content=ft.Column([
                            ft.Row([txt_busca, dd_filtro_etapa]),
                            ft.Row([
                                ft.Text("Filtro de Atraso:", weight="bold", color=ft.Colors.GREY_300),
                                txt_dias_filtro,
                                ft.Text("dias em", size=12, color=ft.Colors.GREY_400),
                                dd_tipo_data,
                                ft.VerticalDivider(width=20, color=ft.Colors.GREY_800),
                                txt_total # Adicionado aqui
                            ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=10)
                        ], spacing=10), 
                        bgcolor=ft.Colors.GREY_900, padding=15, # Fundo Filtros
                        border=ft.border.only(bottom=ft.border.BorderSide(1, ft.Colors.GREY_800))
                    ),
                    # Lista RolÃ¡vel
                    lv_lista
                ], expand=True, spacing=0)
            ),
            ft.Tab(
                text="Dashboard GrÃ¡fico",
                icon=ft.Icons.INSERT_CHART_OUTLINED,
                content=criar_graficos_view(df_user)
            ),
        ],
        expand=True,
    )

    # Header Superior
    header = ft.Container(
        content=ft.Row([
            ft.Column([
                ft.Text(f"OlÃ¡, {user.split('|')[0].strip()}", size=20, weight="bold", color=ft.Colors.AMBER),
                ft.Text("Performance e GestÃ£o", size=12, color=ft.Colors.GREY_400)
            ], spacing=2),
            ft.IconButton(ft.Icons.LOGOUT_ROUNDED, icon_color=ft.Colors.AMBER, tooltip="Sair", 
                        on_click=lambda e: on_logout())
        ], alignment="spaceBetween"),
        bgcolor=ft.Colors.GREY_900, padding=ft.padding.symmetric(horizontal=20, vertical=15),
        shadow=ft.BoxShadow(blur_radius=5, color=ft.Colors.with_opacity(0.5, ft.Colors.BLACK))
    )

    page.add(ft.Column([header, tabs], expand=True, spacing=0))
    atualizar_lista()
```

## views/login.py
```python
import flet as ft

def tela_login(page: ft.Page, colaboradores, on_login_success):
    page.clean()
    
    def entrar(e):
        if dd.value:
            # Flet 0.84+: `page.client_storage` foi removido.
            # Alternativa compatÃ­vel: store da sessÃ£o (transiente, mas suficiente para navegaÃ§Ã£o interna).
            page.session.store.set("user", dd.value)
            on_login_success(dd.value)
        else:
            dd.error_text = "Campo obrigatÃ³rio"
            page.update()

    dd = ft.Dropdown(
        width=320, 
        label="Selecione seu UsuÃ¡rio", 
        options=[ft.dropdown.Option(x) for x in colaboradores],
        bgcolor=ft.Colors.GREY_900, # Fundo escuro
        border_color=ft.Colors.AMBER, # Borda amarela
        border_radius=8,
        text_style=ft.TextStyle(color=ft.Colors.WHITE)
    )

    card_login = ft.Container(
        content=ft.Column([
            ft.Icon(ft.Icons.SECURITY, size=60, color=ft.Colors.AMBER), # Icone Amarelo
            ft.Text("Portal do Colaborador", size=24, weight="bold", color=ft.Colors.WHITE),
            ft.Text("Acesse suas mÃ©tricas e clientes", size=14, color=ft.Colors.GREY_400),
            ft.Divider(height=20, color="transparent"),
            dd,
            ft.ElevatedButton(
                "Entrar no Sistema", 
                on_click=entrar, 
                width=320, height=45,
                style=ft.ButtonStyle(
                    bgcolor=ft.Colors.AMBER, # BotÃ£o Amarelo
                    color=ft.Colors.BLACK,   # Texto Preto (contraste)
                    shape=ft.RoundedRectangleBorder(radius=8)
                )
            )
        ], alignment="center", horizontal_alignment="center", spacing=10),
        padding=40, bgcolor=ft.Colors.GREY_900, border_radius=20, # Card Escuro
        shadow=ft.BoxShadow(blur_radius=15, color=ft.Colors.with_opacity(0.5, ft.Colors.BLACK)),
        width=400
    )

    page.add(ft.Container(content=card_login, alignment=ft.Alignment.CENTER, expand=True))
```

