import { describe, expect, it } from "vitest"

import { parseRedirectUris, urisToText } from "./redirectUris"

describe("parseRedirectUris", () => {
  it("parte una URI por línea", () => {
    expect(
      parseRedirectUris(
        "http://192.168.0.101:8443/auth/callback\nhttps://mobile.ineac.xyz/auth/callback",
      ),
    ).toEqual([
      "http://192.168.0.101:8443/auth/callback",
      "https://mobile.ineac.xyz/auth/callback",
    ])
  })

  it("parte URIs concatenadas por coma en un solo string", () => {
    expect(
      parseRedirectUris(
        "http://192.168.0.101:8443/auth/callback,https://mobile.ineac.xyz/auth/callback",
      ),
    ).toEqual([
      "http://192.168.0.101:8443/auth/callback",
      "https://mobile.ineac.xyz/auth/callback",
    ])
  })

  it("no parte comas de query string", () => {
    expect(parseRedirectUris("https://app.example/callback?ids=1,2")).toEqual([
      "https://app.example/callback?ids=1,2",
    ])
  })

  it("deduplica y recorta vacíos", () => {
    expect(
      parseRedirectUris(
        "https://a.example/cb\n\nhttps://a.example/cb,https://b.example/cb",
      ),
    ).toEqual(["https://a.example/cb", "https://b.example/cb"])
  })
})

describe("urisToText", () => {
  it("expande el formato persistido incorrecto a una URI por línea", () => {
    expect(
      urisToText([
        "http://192.168.0.101:8443/auth/callback,https://mobile.ineac.xyz/auth/callback",
      ]),
    ).toBe(
      "http://192.168.0.101:8443/auth/callback\nhttps://mobile.ineac.xyz/auth/callback",
    )
  })
})
