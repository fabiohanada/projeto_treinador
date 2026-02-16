import { serve } from "https://deno.land/std@0.177.0/http/server.ts"
import { createClient } from "https://esm.sh/@supabase/supabase-js@2"

serve(async (req) => {
  const url = new URL(req.url)

  // 1. VALIDAÇÃO (GET) - Mantemos a lógica que garantiu o 201
  if (req.method === "GET") {
    const challenge = url.searchParams.get("hub.challenge")
    if (challenge) {
      return new Response(JSON.stringify({ "hub.challenge": challenge }), {
        status: 200, headers: { "Content-Type": "application/json" }
      })
    }
  }

  // 2. RECEBIMENTO E SALVAMENTO (POST)
  if (req.method === "POST") {
    try {
      const body = await req.json()
      console.log("🔔 Evento recebido:", body)

      // Conectar ao Supabase (Ele pega a URL e a KEY sozinho do ambiente)
      const supabase = createClient(
        Deno.env.get('SUPABASE_URL') ?? '',
        Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? ''
      )

      // Salvar na tabela 'webhook_events'
      const { error } = await supabase
        .from('webhook_events')
        .insert({ event_data: body })

      if (error) console.error("Erro ao salvar:", error)
      else console.log("✅ Evento salvo no banco!")

      return new Response("EVENT_RECEIVED", { status: 200 })
    } catch (err) {
      return new Response("Bad Request", { status: 400 })
    }
  }

  return new Response("Not Found", { status: 404 })
})