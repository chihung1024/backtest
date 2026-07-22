import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { searchAssets } from "../api";
import { TickerInput } from "./TickerInput";

vi.mock("../api", () => ({ searchAssets: vi.fn() }));

const connection = { baseUrl: "https://example.test", accessKey: "" };

describe("TickerInput", () => {
  beforeEach(() => {
    vi.mocked(searchAssets).mockReset();
  });

  it("exposes combobox state and supports keyboard selection", async () => {
    vi.mocked(searchAssets).mockResolvedValue([
      { symbol: "VT", name: "Vanguard Total World", exchange: "NYSE", currency: "USD", quote_type: "ETF" },
      { symbol: "QQQ", name: "Invesco QQQ", exchange: "NASDAQ", currency: "USD", quote_type: "ETF" },
    ]);
    const onChange = vi.fn();

    render(
      <label>
        代碼
        <TickerInput
          value="V"
          connection={connection}
          placeholder="股票／ETF 代碼"
          searchLabel="搜尋代碼"
          clearLabel="清空輸入"
          onChange={onChange}
        />
      </label>,
    );

    const input = screen.getByRole("combobox", { name: "代碼" });
    expect(input).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(screen.getByRole("button", { name: "搜尋代碼" }));
    expect(input).toHaveFocus();

    await waitFor(() => expect(screen.getByRole("listbox")).toBeInTheDocument());
    expect(input).toHaveAttribute("aria-expanded", "true");
    expect(input).toHaveAttribute("aria-activedescendant");

    fireEvent.keyDown(input, { key: "ArrowDown" });
    expect(screen.getByRole("option", { name: /QQQ/ })).toHaveAttribute("aria-selected", "true");
    fireEvent.keyDown(input, { key: "Enter" });

    expect(onChange).toHaveBeenCalledWith("QQQ");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("closes the result list with Escape", async () => {
    vi.mocked(searchAssets).mockResolvedValue([
      { symbol: "VT", name: "Vanguard Total World", exchange: "NYSE", currency: "USD", quote_type: "ETF" },
    ]);

    render(
      <TickerInput
        value="V"
        connection={connection}
        placeholder="股票／ETF 代碼"
        searchLabel="搜尋代碼"
        clearLabel="清空輸入"
        onChange={() => undefined}
      />,
    );

    const input = screen.getByRole("combobox");
    fireEvent.click(screen.getByRole("button", { name: "搜尋代碼" }));
    await waitFor(() => expect(screen.getByRole("listbox")).toBeInTheDocument());
    fireEvent.keyDown(input, { key: "Escape" });
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });
});
