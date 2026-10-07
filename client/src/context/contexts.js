import { createContext, useContext } from "react";

export const AuthContext = createContext(null);
export const PriceContext = createContext(null);

export const useAuth = () => useContext(AuthContext);
export const usePrices = () => useContext(PriceContext);

/** Quote currency configured on the backend (QUOTE_CURRENCY), e.g. "USDT". */
export const useQuoteCurrency = () => useContext(PriceContext)?.data?.quote_currency ?? "USDT";
