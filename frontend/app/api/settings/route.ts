import { NextRequest } from 'next/server';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8010';

export async function GET() {
  try {
    const res = await fetch(`${API_BASE}/api/settings`, { cache: 'no-store' });
    const text = await res.text();
    return new Response(text, { status: res.status, headers: { 'content-type': 'application/json' } });
  } catch {
    return new Response(JSON.stringify({ error: 'Could not connect to backend' }), { status: 502, headers: { 'content-type': 'application/json' } });
  }
}

export async function PUT(request: NextRequest) {
  const payload = await request.text();
  try {
    const res = await fetch(`${API_BASE}/api/settings`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: payload });
    const text = await res.text();
    return new Response(text, { status: res.status, headers: { 'content-type': 'application/json' } });
  } catch {
    return new Response(JSON.stringify({ error: 'Could not connect to backend' }), { status: 502, headers: { 'content-type': 'application/json' } });
  }
}
