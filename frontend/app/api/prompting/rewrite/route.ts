import { NextRequest } from 'next/server';

export async function POST(request: NextRequest) {
  const payload = await request.json();
  const base = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8010';
  const res = await fetch(`${base}/api/prompting/rewrite`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const text = await res.text();
  return new Response(text, { status: res.status, headers: { 'content-type': 'application/json' } });
}
