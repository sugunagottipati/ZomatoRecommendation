import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function normalizeBaseUrl(value: string | undefined): string | null {
  if (!value) {
    return null;
  }

  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }

  try {
    return new URL(trimmed).toString().replace(/\/$/, "");
  } catch {
    return null;
  }
}

function resolveBackendBaseUrl(): string | null {
  return (
    normalizeBaseUrl(process.env.API_BASE_URL) ||
    normalizeBaseUrl(process.env.NEXT_PUBLIC_API_BASE_URL) ||
    normalizeBaseUrl(process.env.NODE_ENV === "production" ? undefined : "http://localhost:8000")
  );
}

async function proxy(request: NextRequest, pathParts: string[]): Promise<NextResponse> {
  const backendBaseUrl = resolveBackendBaseUrl();

  if (!backendBaseUrl) {
    return NextResponse.json(
      {
        detail:
          "Backend URL is not configured. Set API_BASE_URL in Vercel project environment variables.",
      },
      { status: 503 },
    );
  }

  const safePath = pathParts.join("/");
  const upstreamUrl = `${backendBaseUrl}/${safePath}${request.nextUrl.search}`;

  try {
    const requestHeaders = new Headers(request.headers);
    requestHeaders.delete("host");
    requestHeaders.delete("connection");
    requestHeaders.delete("content-length");

    const method = request.method.toUpperCase();
    const hasBody = method !== "GET" && method !== "HEAD";

    const upstreamResponse = await fetch(upstreamUrl, {
      method,
      headers: requestHeaders,
      body: hasBody ? await request.arrayBuffer() : undefined,
      redirect: "manual",
      cache: "no-store",
    });

    const payload = await upstreamResponse.arrayBuffer();

    const responseHeaders = new Headers(upstreamResponse.headers);
    responseHeaders.delete("content-encoding");
    responseHeaders.delete("transfer-encoding");
    responseHeaders.delete("connection");

    return new NextResponse(payload, {
      status: upstreamResponse.status,
      headers: responseHeaders,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Upstream request failed";
    return NextResponse.json({ detail: message }, { status: 502 });
  }
}

type RouteContext = {
  params: Promise<{ path: string[] }>;
};

export async function GET(request: NextRequest, context: RouteContext): Promise<NextResponse> {
  const { path } = await context.params;
  return proxy(request, path);
}

export async function POST(request: NextRequest, context: RouteContext): Promise<NextResponse> {
  const { path } = await context.params;
  return proxy(request, path);
}

export async function PUT(request: NextRequest, context: RouteContext): Promise<NextResponse> {
  const { path } = await context.params;
  return proxy(request, path);
}

export async function PATCH(request: NextRequest, context: RouteContext): Promise<NextResponse> {
  const { path } = await context.params;
  return proxy(request, path);
}

export async function DELETE(request: NextRequest, context: RouteContext): Promise<NextResponse> {
  const { path } = await context.params;
  return proxy(request, path);
}
