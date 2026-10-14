import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Em desenvolvimento a API (FastAPI) corre na porta 8000; o Vite reencaminha
// /api para lá, por isso o browser vê tudo na mesma origem (o cookie de
// sessão funciona sem CORS).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5180,
    strictPort: true,
    proxy: { "/api": "http://localhost:8000" },
  },
});
