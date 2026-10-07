import { createContext, useContext } from "react";

export const AuthContext = createContext(null);
export const PriceContext = createContext(null);

export const useAuth = () => useContext(AuthContext);
export const usePrices = () => useContext(PriceContext);
