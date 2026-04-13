import { NextRequest } from 'next/server';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8010';

export async function POST(request: NextRequest) {
  const payload = await request.json();
  try {
    const res = await fetch(`${API_BASE}/api/prompting/rewrite`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const text = await res.text();
    return new Response(text, { status: res.status, headers: { 'content-type': 'application/json' } });
  } catch {
    return new Response(JSON.stringify({ error: 'Could not connect to backend' }), { status: 502, headers: { 'content-type': 'application/json' } });
  }
}
