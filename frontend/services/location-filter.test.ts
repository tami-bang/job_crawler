import { describe, expect, it } from "vitest";
import { isCapitalAreaLocation } from "./location-filter";

describe("capital area location filter", () => {
  it("allows only Seoul, Gyeonggi and Incheon", () => {
    expect(isCapitalAreaLocation("서울 강남구")).toBe(true);
    expect(isCapitalAreaLocation("경기 성남시")).toBe(true);
    expect(isCapitalAreaLocation("인천 연수구")).toBe(true);
    expect(isCapitalAreaLocation("충북 청주시")).toBe(false);
    expect(isCapitalAreaLocation("부산 해운대구")).toBe(false);
  });

  it("allows capital-area-led multi-region and missing locations", () => {
    expect(isCapitalAreaLocation(null)).toBe(true);
    expect(isCapitalAreaLocation("서울 외 14")).toBe(true);
  });
});
