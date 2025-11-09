import { Response } from 'express';

export const successResponse = (res: Response, data: any, message?: string, statusCode = 200) => {
  return res.status(statusCode).json({
    success: true,
    message: message || 'Success',
    data,
  });
};

export const errorResponse = (res: Response, message: string, statusCode = 500, errors?: any) => {
  return res.status(statusCode).json({
    success: false,
    message,
    errors,
  });
};