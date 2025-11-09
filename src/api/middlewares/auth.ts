import { Request, Response, NextFunction } from 'express';
import { auth } from '../../config';
import { errorResponse } from '../utils/responseBuilder';
import logger from '../utils/logger';

export interface AuthRequest extends Request {
  user?: {
    uid: string;
    email?: string;
    email_verified?: boolean;
  };
}

export const authenticateUser = async (
  req: AuthRequest,
  res: Response,
  next: NextFunction
) => {
  try {
    const authHeader = req.headers.authorization;

    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return errorResponse(res, 'Missing or invalid authorization header', 401);
    }

    const token = authHeader.split('Bearer ')[1];

    const decodedToken = await auth.verifyIdToken(token);

    req.user = {
      uid: decodedToken.uid,
      email: decodedToken.email,
      email_verified: decodedToken.email_verified,
    };

    logger.debug(`User authenticated: ${req.user.uid}`);
    next();
  } catch (error: any) {
    logger.error('Authentication error:', error);
    return errorResponse(res, 'Invalid or expired token', 401);
  }
};