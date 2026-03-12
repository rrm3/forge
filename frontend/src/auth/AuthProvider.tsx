import { createContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import {
  AuthenticationDetails,
  CognitoUser,
  type CognitoUserSession,
} from 'amazon-cognito-identity-js';
import { userPool } from './cognito';
import { setTokenGetter } from '../api/client';
import { setChatTokenGetter } from '../api/chat';

interface AuthUser {
  userId: string;
  email: string;
  name: string;
}

interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  user: AuthUser | null;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => void;
  getToken: () => Promise<string | null>;
}

export const AuthContext = createContext<AuthContextType | null>(null);

function getUserFromSession(session: CognitoUserSession): AuthUser {
  const payload = session.getIdToken().decodePayload();
  return {
    userId: payload['sub'] as string,
    email: (payload['email'] as string) || '',
    name: (payload['name'] as string) || (payload['email'] as string) || '',
  };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const cognitoUser = userPool.getCurrentUser();
    if (!cognitoUser) {
      setIsLoading(false);
      return;
    }

    cognitoUser.getSession((err: Error | null, session: CognitoUserSession | null) => {
      if (err || !session || !session.isValid()) {
        setIsLoading(false);
        return;
      }
      setUser(getUserFromSession(session));
      setIsLoading(false);
    });
  }, []);

  const signIn = useCallback(async (email: string, password: string): Promise<void> => {
    const authDetails = new AuthenticationDetails({
      Username: email,
      Password: password,
    });

    const cognitoUser = new CognitoUser({
      Username: email,
      Pool: userPool,
    });

    return new Promise((resolve, reject) => {
      cognitoUser.authenticateUser(authDetails, {
        onSuccess: (session) => {
          setUser(getUserFromSession(session));
          resolve();
        },
        onFailure: (err) => {
          reject(err);
        },
        newPasswordRequired: () => {
          reject(new Error('Password change required. Contact your administrator.'));
        },
      });
    });
  }, []);

  const signOut = useCallback(() => {
    const cognitoUser = userPool.getCurrentUser();
    if (cognitoUser) {
      cognitoUser.signOut();
    }
    setUser(null);
  }, []);

  const getToken = useCallback(async (): Promise<string | null> => {
    return new Promise((resolve) => {
      const cognitoUser = userPool.getCurrentUser();
      if (!cognitoUser) {
        resolve(null);
        return;
      }

      cognitoUser.getSession((err: Error | null, session: CognitoUserSession | null) => {
        if (err || !session || !session.isValid()) {
          resolve(null);
          return;
        }
        resolve(session.getIdToken().getJwtToken());
      });
    });
  }, []);

  // Register the token getter with the API client so requests are authenticated
  useEffect(() => {
    setTokenGetter(getToken);
    setChatTokenGetter(getToken);
  }, [getToken]);

  const value: AuthContextType = {
    isAuthenticated: user !== null,
    isLoading,
    user,
    signIn,
    signOut,
    getToken,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
