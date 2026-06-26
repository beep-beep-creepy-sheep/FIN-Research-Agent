import { describe, expect, it } from "vitest";
import { API_ROUTES } from "../../src/lib/api";

describe("frontend API route contract", () => {
  it("uses canonical routes while documenting compatibility aliases", () => {
    expect(API_ROUTES.companyCharts("600519")).toBe("/v1/companies/600519/charts");
    expect(API_ROUTES.companyChartAlias("600519")).toBe("/v1/companies/600519/chart");
    expect(API_ROUTES.screenerQuery).toBe("/v1/screener/query");
    expect(API_ROUTES.screensQueryAlias).toBe("/v1/screens/query");
  });
});
