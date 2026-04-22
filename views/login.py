import flet as ft

def tela_login(page: ft.Page, colaboradores, on_login_success):
    page.clean()
    
    def entrar(e):
        if dd.value:
            # Flet 0.84+: `page.client_storage` foi removido.
            # Alternativa compatível: store da sessão (transiente, mas suficiente para navegação interna).
            page.session.store.set("user", dd.value)
            on_login_success(dd.value)
        else:
            dd.error_text = "Campo obrigatório"
            page.update()

    dd = ft.Dropdown(
        width=320, 
        label="Selecione seu Usuário", 
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
            ft.Text("Acesse suas métricas e clientes", size=14, color=ft.Colors.GREY_400),
            ft.Divider(height=20, color="transparent"),
            dd,
            ft.ElevatedButton(
                "Entrar no Sistema", 
                on_click=entrar, 
                width=320, height=45,
                style=ft.ButtonStyle(
                    bgcolor=ft.Colors.AMBER, # Botão Amarelo
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
