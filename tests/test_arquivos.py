import io
import unittest

import _setup  # noqa: F401
from esg_core.arquivos import extrair_texto


def pdf_com_texto(texto: str) -> bytes:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    matplotlib.rcParams["pdf.fonttype"] = 42
    fig = plt.figure(figsize=(6, 3))
    fig.text(0.05, 0.5, texto)
    buf = io.BytesIO()
    fig.savefig(buf, format="pdf")
    plt.close(fig)
    return buf.getvalue()


class ArquivosTests(unittest.TestCase):
    def test_texto_e_codificacoes(self):
        self.assertEqual(extrair_texto("a.txt", "emissões".encode("utf-8"))[0], "emissões")
        self.assertEqual(extrair_texto("a.md", "emissões".encode("latin-1"))[0], "emissões")

    def test_formato_nao_suportado(self):
        with self.assertRaises(ValueError) as cm:
            extrair_texto("planilha.xlsx", b"x")
        self.assertIn(".pdf", str(cm.exception))

    def test_pdf(self):
        try:
            import pypdf  # noqa: F401
        except ImportError:
            self.skipTest("pypdf não instalado")
        texto, avisos = extrair_texto("rel.pdf", pdf_com_texto("Relatorio de sustentabilidade 2025 reduziu 12 por cento"))
        self.assertIn("sustentabilidade", texto)
        self.assertEqual(avisos, [])
        sem_texto, avisos = extrair_texto("vazio.pdf", pdf_com_texto(""))
        self.assertEqual(sem_texto, "")
        self.assertIn("escaneado", avisos[0])


if __name__ == "__main__":
    unittest.main()
