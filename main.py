import flet as ft
import pandas as pd
import matplotlib

# Matplotlib em modo headless (Windows + Flet Desktop).
# Importante: definir backend ANTES de importar pyplot.
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from datetime import datetime
#agora vamos converter para onboarding

# --- IMPORTAÇÕES DO SERVIÇO (API) ---
import service
from service import load_sittax, load_user_data, USER_MAP, get_deal_activities, search_users
from utils import MatplotlibChart

# Configuração do Matplotlib

# Alias para facilitar
Colors = ft.Colors
Icons = ft.Icons

async def main(page: ft.Page):
    # --- CONFIGURAÇÃO DA PÁGINA ---
    page.title = "Sittax - Portal do Colaborador"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 0
    page.bgcolor = "#121212"
    page.fonts = {
        "Roboto": "https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap"
    }

    # --- COMPATIBILIDADE FLET 0.84+ ---
    # `page.splash`, `page.snack_bar` e `page.open()` nÃ£o sÃ£o mais as APIs recomendadas.
    # Helpers simples para manter a lÃ³gica do app sem crashes.
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
        Se já houver um aberto, tentamos fechar e abrir o novo de forma segura.
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
    
    # --- 1. INICIALIZAÇÃO DE DADOS ---
    # Carrega a base estática do Sittax uma única vez ao iniciar
    print("Inicializando aplicação...")
    df_sittax_global = load_sittax()
    sittax_error = service.LAST_SITTAX_ERROR
    
    # Variáveis globais de estado
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
        login_running = {"value": False}
        users_loaded = {"value": False}
        users_loading = {"value": False}

        async def carregar_todos_usuarios(force: bool = False):
            """
            Carrega todos os usuários do Pipedrive no dropdown.

            Pedido: ao clicar/expandir o dropdown, preencher a lista mesmo sem
            digitar nada no campo de busca.
            """
            if users_loading["value"]:
                return
            if users_loaded["value"] and not force:
                return

            users_loading["value"] = True
            dd_users.error_text = None
            dd_users.label = "Carregando usuários..."
            btn_busca.disabled = True
            page.update()

            try:
                users = await service.list_users_async()
                if users:
                    dd_users.options = [
                        ft.dropdown.Option(key=str(u["id"]), text=f"{u['name']} ({u.get('email','')})")
                        for u in users
                    ]
                    dd_users.value = None
                    dd_users.label = "Selecione o usuário"
                    users_loaded["value"] = True
                    btn_entrar.disabled = True
                else:
                    dd_users.options = []
                    dd_users.value = None
                    dd_users.label = "Nenhum usuário retornado"
                    show_snack("A API não retornou usuários. Verifique permissões do token.")
            except Exception as ex:
                dd_users.options = []
                dd_users.value = None
                dd_users.label = "Falha ao carregar usuários"
                show_snack(f"Erro ao listar usuários: {ex}")
            finally:
                btn_busca.disabled = False
                users_loading["value"] = False
                page.update()

        async def buscar_click(e):
            term = (txt_busca_user.value or "").strip()

            # Se não houver busca suficiente, carrega TODOS os usuários.
            if not term or len(term) < 2:
                await carregar_todos_usuarios(force=True)
                return

            dd_users.error_text = None
            btn_busca.disabled = True
            page.update()

            try:
                users = search_users(term)
                if users:
                    dd_users.options = [
                        ft.dropdown.Option(key=str(u["id"]), text=f"{u['name']} ({u['email']})")
                        for u in users
                    ]
                    dd_users.value = None
                    dd_users.label = "Selecione o usuário encontrado"

                    # Se só tiver um, pré-seleciona
                    if len(users) == 1:
                        u = users[0]
                        dd_users.value = str(u["id"])
                        selected_user_data["id"] = u["id"]
                        selected_user_data["name"] = u["name"]
                        btn_entrar.disabled = False
                else:
                    dd_users.options = []
                    dd_users.value = None
                    dd_users.label = "Nenhum usuário encontrado"
                    btn_entrar.disabled = True
            except Exception as ex:
                dd_users.error_text = f"Erro: {ex}"
            finally:
                btn_busca.disabled = False
                page.update()

        def on_user_change(e):
            if dd_users.value:
                uid = int(dd_users.value)
                # Pega o nome do texto da opção
                opt_text = next((o.text for o in dd_users.options if o.key == dd_users.value), "Usuário")
                uname = opt_text.split(" (")[0] # Remove o email do display
                
                selected_user_data["id"] = uid
                selected_user_data["name"] = uname
                btn_entrar.disabled = False
            else:
                btn_entrar.disabled = True
            page.update()

        async def entrar(e):
            # Evita múltiplos cliques/disparos enquanto a requisição está em andamento.
            if login_running["value"]:
                return
            if selected_user_data["id"]:
                login_running["value"] = True
                user_name = selected_user_data["name"]
                user_id = selected_user_data["id"]
                
                # Feedback de Carregamento
                btn_entrar.disabled = True
                btn_entrar.text = "Buscando dados na API..."
                show_loading("Buscando dados na API...")

                try:
                    # --- CHAMADA À API ---
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
                        show_snack(
                            "Nenhum negócio retornado pela API para este usuário. "
                            "Verifique se ele tem negócios abertos ou se o token do Pipedrive tem permissão/visibilidade para ver a carteira."
                        )
                        page.update()

                except Exception as ex:
                    print(f"Erro no login: {ex}")
                    hide_loading()
                    btn_entrar.disabled = False
                    btn_entrar.text = "Entrar no Sistema"
                    show_snack(f"Erro de conexão: {ex}")
                    page.update()
                finally:
                    login_running["value"] = False

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
            label="Clique para carregar usuários",
            options=[],
            disabled=False,
            bgcolor=Colors.GREY_900,
            border_color=Colors.GREY_700,
            border_radius=8,
            text_style=ft.TextStyle(color=Colors.WHITE),
            # Flet 0.84+: Dropdown não usa `on_change`; use `on_select`.
        )
        dd_users.on_select = on_user_change

        def on_users_focus(e):
            # Importante: não bloqueia o clique/expansão do dropdown com um `await`.
            # Carrega em background; se ainda não abriu, o usuário clica de novo e já terá lista.
            if not dd_users.options and not users_loading["value"]:
                page.run_task(carregar_todos_usuarios, False)

        def on_users_text_change(e):
            # Fallback: se o usuário começar a digitar e ainda não carregou, carrega em background.
            if not dd_users.options and not users_loading["value"]:
                page.run_task(carregar_todos_usuarios, False)

        # Ao focar (clicar) no dropdown, carrega todos os usuários automaticamente.
        dd_users.on_focus = on_users_focus
        dd_users.on_text_change = on_users_text_change

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
                ft.Text("Busque seu usuário Pipedrive", size=14, color=Colors.GREY_400),
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

        # Pré-carrega a lista de usuários em background para o dropdown já abrir com opções.
        page.run_task(carregar_todos_usuarios, False)

    def tela_painel(user, user_id=None):
        page.clean()
        
        # O DataFrame em dados["df"] já é filtrado para o usuário pela API, 
        # mas mantemos o filtro por segurança/consistência
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
            show_snack("Copiado para área de transferência!")
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
                email = str(row.get('Organização - E-mail', '') or row.get('Pessoa - E-mail', 'N/A'))
                
                # Telefone
                tel = str(row.get('Organização - Telefone', 'N/A'))
                tel_clean = ''.join(filter(str.isdigit, tel))

                status = str(row.get('Status', ''))
                etapa = str(row.get('Negócio - Etapa', ''))
                dias_ativ = int(row.get('Dias_Sem_Ativ', 0))
                dias_etapa = int(row.get('Dias_Sem_Etapa', 0))
                
                mensalidade = float(row.get('Negócio - Mensalidade', 0.0))
                usabilidade = str(row.get('Usabilidade', '-'))
                ult_acesso = str(row.get('Ult_Acesso', '-'))

                # Formata o documento para exibição
                cnpj_fmt = format_document(cnpj)

                cor_st = Colors.RED_ACCENT if "Risco" in status else Colors.GREEN
                
                # Container para atividades (carregado dinamicamente)
                col_atividades = ft.Column(spacing=5)
                loading_atividades = ft.ProgressBar(width=100, color=Colors.AMBER, visible=True)
                
                def carregar_atividades_async():
                    try:
                        # Pega o ID do negócio (precisamos garantir que está no DF)
                        deal_id = row.get('id') # Isso é booleano no DF atual, precisamos do ID real
                        # Como o DF atual não tem o ID do deal explícito na coluna, vamos tentar inferir ou buscar
                        # Melhor abordagem: Adicionar 'id' (deal_id) no PIPE_BASE_COLUMNS em service.py e recarregar
                        # Por enquanto, vamos assumir que precisamos ajustar o service.py primeiro para trazer o ID.
                        pass
                    except:
                        pass

                # Ajuste temporário: Vamos buscar atividades usando o CNPJ/Key para encontrar o deal_id no DF em memória se possível
                # Mas o ideal é ter o deal_id direto. Vamos usar o que temos.
                # O service.py não exporta o deal_id explicitamente no PIPE_BASE_COLUMNS.
                # Vamos adicionar o deal_id no service.py primeiro? Não, o usuário pediu para ser rápido.
                # Vamos assumir que o 'Tem_Atividade_Aberta' é apenas um flag.
                
                # CORREÇÃO: O service.py precisa retornar o ID do Deal para podermos buscar as atividades dele.
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
                            ft.Text("Últ. Acesso", size=12, color=Colors.GREY_400),
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
                    ft.Text("Métricas de Tempo:", weight="bold", size=14, color=Colors.WHITE),
                    ft.Row([
                        ft.Text(f"⏱️ {dias_ativ} dias sem atividade", color=Colors.ORANGE_ACCENT if dias_ativ > 15 else Colors.GREY_400),
                        ft.Text(f"📅 {dias_etapa} dias nesta etapa", color=Colors.GREY_400)
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
                        # Filtra por deal_id E pelo usuário logado para garantir que só veja suas tarefas neste deal
                        # O user_id logado vem do Pipedrive (selecionado no login).
                        # Usar USER_MAP pode falhar para usuários fora do mapeamento legado.
                        ats = get_deal_activities(deal_id, owner_id=user_id)
                        
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
                    
                    # Executa em thread separada para não travar a UI
                    import threading
                    threading.Thread(target=carregar_ativs, daemon=True).start()
                else:
                    loading_atividades.visible = False
                    col_atividades.controls.append(ft.Text("ID do negócio não encontrado.", color=Colors.RED_400, size=12))
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
                res = res[res['Negócio - Etapa'] == dd_filtro_etapa.value]
            
            # 3. Filtro Dias
            try:
                dias_corte = int(txt_dias_filtro.value)
            except:
                dias_corte = 0
            
            if dias_corte > 0:
                coluna_filtro = 'Dias_Sem_Ativ' if dd_tipo_data.value == "ativ" else 'Dias_Sem_Etapa'
                if coluna_filtro in res.columns:
                    res = res[res[coluna_filtro] > dias_corte]

            # 4. Ordenação
            if dd_ordenacao.value == "nome":
                res = res.sort_values(by="Nome", ascending=True)
            elif dd_ordenacao.value == "valor_desc":
                res = res.sort_values(by="Negócio - Mensalidade", ascending=False)
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
                    et = str(row.get('Negócio - Etapa', '-'))
                    
                    uf = str(row.get('Organização - Estado de Endereço', '-'))
                    if uf == 'nan': uf = '-'
                    
                    raw_tel = str(row.get('Organização - Telefone', '-'))
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
                    valor_mensal = float(row.get('Negócio - Mensalidade', 0.0))
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
                                        tooltip="Copiar apenas números",
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
        # Flet 0.84+: Dropdown não usa `on_change`; use `on_select`.
        dd_filtro_etapa.on_select = atualizar_lista
        txt_dias_filtro.on_change = atualizar_lista
        dd_tipo_data.on_select = atualizar_lista
        dd_ordenacao.on_select = atualizar_lista

        # --- ABA 2: GRÁFICOS ---
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

            # Gráfico 1: Barras (Etapas)
            fig1, ax1 = plt.subplots(figsize=(6, 4))
            fig1.patch.set_alpha(0)
            ax1.set_facecolor('#212121')
            
            if 'Negócio - Etapa' in df_user.columns:
                d_etapa = df_user['Negócio - Etapa'].value_counts().head(6)
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

            # Gráfico 2: Pizza (Status Sittax)
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

            # Gráfico 3: Receita Mensal por Etapa (MRR)
            fig3, ax3 = plt.subplots(figsize=(6, 4))
            fig3.patch.set_alpha(0)
            ax3.set_facecolor('#212121')
            
            if 'Negócio - Mensalidade' in df_user.columns and 'Negócio - Etapa' in df_user.columns:
                d_mrr = df_user.groupby('Negócio - Etapa')['Negócio - Mensalidade'].sum().sort_values(ascending=True).tail(6)
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

            # Gráfico 4: Migrações no Mês Atual
            fig4, ax4 = plt.subplots(figsize=(6, 4))
            fig4.patch.set_alpha(0)
            ax4.set_facecolor('#212121')
            
            migracoes_mes = 0
            if 'Data_Mudanca_Etapa' in df_user.columns:
                # Filtra datas válidas e do mês atual
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
            
            # Mostra apenas um número grande
            ax4.text(0.5, 0.6, str(migracoes_mes), ha='center', va='center', fontsize=40, color='#66bb6a', weight='bold')
            ax4.text(0.5, 0.3, 'Mudanças de Etapa este Mês', ha='center', va='center', fontsize=12, color='#cccccc')
            ax4.axis('off')

            return ft.ListView([
                ft.Text("Visão Geral da Carteira", size=20, weight="bold", color=Colors.WHITE),
                ft.Text("Indicadores de performance e saúde", size=12, color=Colors.GREY_400, italic=True),
                ft.Divider(height=20, color="transparent"),
                ft.ResponsiveRow([
                    ft.Column([grafico_card("Distribuição do Funil (Qtd)", fig1)], col={"sm": 12, "md": 6}),
                    ft.Column([grafico_card("Saúde Financeira (Status)", fig2)], col={"sm": 12, "md": 6}),
                    ft.Column([grafico_card("Receita Mensal por Etapa (MRR)", fig3)], col={"sm": 12, "md": 6}),
                    ft.Column([grafico_card("Produtividade Recente", fig4)], col={"sm": 12, "md": 6}),
                ])
            ], padding=20, expand=True)

        # --- LAYOUT PRINCIPAL ---
        # Flet 0.84+: Tabs mudou. Agora o controle `ft.Tabs` funciona como um
        # "DefaultTabController" e o conteúdo deve conter um `TabBar` e um `TabBarView`.
        tab_lista = ft.Column(
            [
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Row([txt_busca, dd_filtro_etapa]),
                            ft.Row(
                                [
                                    ft.Text("Filtro de Atraso:", weight="bold", color=Colors.GREY_300),
                                    txt_dias_filtro,
                                    ft.Text("dias em", size=12, color=Colors.GREY_400),
                                    dd_tipo_data,
                                    dd_ordenacao,
                                    ft.VerticalDivider(width=20, color=Colors.GREY_800),
                                    txt_total,
                                ],
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                spacing=10,
                            ),
                        ],
                        spacing=10,
                    ),
                    bgcolor=Colors.GREY_900,
                    padding=15,
                    border=ft.Border(bottom=ft.BorderSide(1, Colors.GREY_800)),
                ),
                lv_lista,
            ],
            expand=True,
            spacing=0,
        )

        tab_graficos = criar_graficos()

        tab_bar = ft.TabBar(
            tabs=[
                ft.Tab(label="Lista & Ações", icon=Icons.LIST_ALT_ROUNDED),
                ft.Tab(label="Dashboard Gráfico", icon=Icons.INSERT_CHART_OUTLINED),
            ],
            scrollable=False,
            indicator_color=Colors.AMBER,
            label_color=Colors.AMBER,
            unselected_label_color=Colors.GREY_400,
            divider_color=Colors.GREY_800,
        )

        tab_view = ft.TabBarView(
            controls=[tab_lista, tab_graficos],
            expand=True,
        )

        tabs = ft.Tabs(
            content=ft.Column([tab_bar, tab_view], expand=True, spacing=0),
            length=2,
            selected_index=0,
            animation_duration=300,
            expand=True,
        )

        async def atualizar_dados(e):
            show_loading("Atualizando dados...")
            
            try:
                # Força recarga da API
                resultado = await service.load_user_data_async(user, df_sittax_global, user_id=user_id, force_refresh=True)
                
                if resultado and not resultado['df'].empty:
                    dados["df"] = resultado["df"]
                    dados["etapas"] = resultado["etapas"]
                    
                    hide_loading()
                    show_snack("Dados atualizados com sucesso!")
                    tela_painel(user) # Recarrega a tela
                else:
                    hide_loading()
                    show_snack("Não foi possível atualizar os dados.")
                    page.update()
            except Exception as ex:
                hide_loading()
                print(f"Erro ao atualizar: {ex}")
                show_snack(f"Erro: {ex}")
                page.update()

        # --- EXPORTAÇÃO ---
        # Flet 0.84+: FilePicker não usa mais `on_result`; agora `save_file()` é async e retorna o caminho.
        file_picker = ft.FilePicker()
        # Flet 0.84+: `FilePicker` é um *Service* (não um Control). Deve ser registrado em `page.services`.
        page.services.append(file_picker)

        async def exportar_dados(e):
            try:
                path = await file_picker.save_file(
                    allowed_extensions=["xlsx"],
                    file_name=f"relatorio_clientes_{datetime.now().strftime('%Y%m%d')}.xlsx",
                )
                if not path:
                    return

                if not path.endswith(".xlsx"):
                    path += ".xlsx"
                df_user.to_excel(path, index=False)
                show_snack(f"Relatório salvo em: {path}")
                page.update()
            except Exception as ex:
                show_snack(f"Erro ao salvar: {ex}")
                page.update()

        header = ft.Container(
            content=ft.Row([
                ft.Column([
                    ft.Text(f"Olá, {user.split('|')[0].strip()}", size=20, weight="bold", color=Colors.AMBER),
                    ft.Text("Performance e Gestão", size=12, color=Colors.GREY_400)
                ], spacing=2),
                ft.Row([
                    ft.IconButton(Icons.DOWNLOAD, icon_color=Colors.AMBER, tooltip="Exportar Excel", on_click=exportar_dados),
                    ft.IconButton(Icons.REFRESH, icon_color=Colors.AMBER, tooltip="Atualizar Dados", on_click=atualizar_dados),
                    ft.IconButton(Icons.LOGOUT_ROUNDED, icon_color=Colors.AMBER, tooltip="Sair", 
                                # Flet 0.84+: `page.client_storage` removido -> store da sessÃ£o.
                                on_click=lambda e: [page.session.store.clear(), tela_login()])
                ])
            ], alignment="spaceBetween"),
            bgcolor=Colors.GREY_900, padding=ft.padding.symmetric(horizontal=20, vertical=15),
            shadow=ft.BoxShadow(blur_radius=5, color=ft.Colors.with_opacity(0.5, Colors.BLACK))
        )

        page.add(ft.Column([header, tabs], expand=True, spacing=0))
        atualizar_lista()

    # --- START ---
    # Verifica se já existe sessão salva, mas força recarregar dados da API
    # para garantir que os dados não estejam obsoletos.
    # Flet 0.84+: `page.client_storage` removido -> store da sessÃ£o.
    u = page.session.store.get("user")
    if u and u in dados["colaboradores"]:
        # Opcional: Poderia ir direto pro painel se persistisse o DF, 
        # mas como o DF está em memória, melhor ir pro login para recarregar.
        # Para UX melhor, preenchemos o dropdown.
        tela_login()
        # Se quiser auto-login real, precisaria chamar load_user_data aqui e mostrar splash.
    else:
        tela_login()

if __name__ == "__main__":
    # Flet 0.84+: `ft.app()` estÃ¡ deprecated. Use `ft.run()`.
    ft.run(main)
