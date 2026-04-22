import flet as ft

from utils import criar_linha_copia, format_document


def show_details_dialog(page: ft.Page, key: str, df_user):
    """
    Fallback mínimo para compatibilidade:
    - `views/dashboard.py` importava `views.details`, mas o módulo não existia.
    - Esta função exibe um dialog com os principais dados do cliente sem quebrar o app.
    """
    try:
        filtro = df_user[df_user["Key"].astype(str) == str(key)]
        if filtro.empty:
            page.show_dialog(ft.SnackBar(ft.Text("Cliente não encontrado.")))
            return

        row = filtro.iloc[0]

        nome = str(row.get("Nome", "-"))
        email = str(row.get("Organização - E-mail", "") or row.get("Pessoa - E-mail", "") or "-")
        status = str(row.get("Status", "-"))
        etapa = str(row.get("Negócio - Etapa", "-"))
        mensalidade = row.get("Negócio - Mensalidade", 0)
        try:
            mensalidade = float(mensalidade or 0)
        except Exception:
            mensalidade = 0.0

        doc_fmt = format_document(str(key))

        content = ft.Column(
            [
                ft.Text(nome, size=18, weight="bold", color=ft.Colors.AMBER),
                ft.Text(email, size=12, color=ft.Colors.GREY_400),
                ft.Divider(color=ft.Colors.GREY_800),
                criar_linha_copia("CNPJ/CPF", doc_fmt, ft.Icons.BADGE, page, valor_limpo=doc_fmt),
                criar_linha_copia("Status", status, ft.Icons.SHIELD, page),
                criar_linha_copia("Etapa", etapa, ft.Icons.TIMELINE, page),
                criar_linha_copia("Mensalidade", f"R$ {mensalidade:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), ft.Icons.PAID, page),
            ],
            tight=True,
            spacing=8,
            scroll=ft.ScrollMode.AUTO,
        )

        dlg = ft.AlertDialog(
            title=ft.Text("Ficha do Cliente", color=ft.Colors.AMBER),
            content=ft.Container(content=content, width=450, height=420),
            bgcolor=ft.Colors.GREY_900,
            modal=True,
        )
        page.show_dialog(dlg)
    except Exception as ex:
        # Não deixa erro de dialog derrubar a aplicação.
        page.show_dialog(ft.SnackBar(ft.Text(f"Erro ao abrir detalhes: {ex}")))
