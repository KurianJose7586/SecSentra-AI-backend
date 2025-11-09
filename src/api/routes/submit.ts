import { Router } from 'express';
import { AuthRequest, authenticateUser } from '../middlewares/auth';
import { successResponse, errorResponse } from '../utils/responseBuilder';
import { db } from '../../config';
import logger from '../utils/logger';

const router = Router();

router.post('/', authenticateUser, async (req: AuthRequest, res) => {
  try {
    const { fileType, fileName, filePath } = req.body;
    const userId = req.user!.uid;

    if (!fileType || !fileName || !filePath) {
      return errorResponse(res, 'Missing required fields', 400);
    }

    const jobId = `job_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

    const jobData = {
      jobId,
      userId,
      fileType,
      fileName,
      filePath,
      status: 'pending',
      classification: 'pending',
      confidence: 0,
      findings: [],
      createdAt: new Date(),
      updatedAt: new Date(),
    };

    await db.collection('jobs').doc(jobId).set(jobData);

    logger.info(`Job created: ${jobId} for user: ${userId}`);

    return successResponse(res, { jobId }, 'Job submitted successfully', 201);
  } catch (error: any) {
    logger.error('Submit error:', error);
    return errorResponse(res, 'Failed to submit job', 500);
  }
});

export default router;