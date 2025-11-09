import { Router } from 'express';
import { AuthRequest, authenticateUser } from '../middlewares/auth';
import { successResponse, errorResponse } from '../utils/responseBuilder';
import { db } from '../../config';
import logger from '../utils/logger';

const router = Router();

router.get('/:jobId/status', authenticateUser, async (req: AuthRequest, res) => {
  try {
    const { jobId } = req.params;
    const userId = req.user!.uid;

    const jobDoc = await db.collection('jobs').doc(jobId).get();

    if (!jobDoc.exists) {
      return errorResponse(res, 'Job not found', 404);
    }

    const jobData = jobDoc.data();

    if (jobData?.userId !== userId) {
      return errorResponse(res, 'Unauthorized access', 403);
    }

    return successResponse(res, {
      jobId,
      status: jobData.status,
      classification: jobData.classification,
      confidence: jobData.confidence,
    });
  } catch (error: any) {
    logger.error('Get job status error:', error);
    return errorResponse(res, 'Failed to get job status', 500);
  }
});

router.get('/:jobId/results', authenticateUser, async (req: AuthRequest, res) => {
  try {
    const { jobId } = req.params;
    const userId = req.user!.uid;

    const jobDoc = await db.collection('jobs').doc(jobId).get();

    if (!jobDoc.exists) {
      return errorResponse(res, 'Job not found', 404);
    }

    const jobData = jobDoc.data();

    if (jobData?.userId !== userId) {
      return errorResponse(res, 'Unauthorized access', 403);
    }

    return successResponse(res, jobData);
  } catch (error: any) {
    logger.error('Get job results error:', error);
    return errorResponse(res, 'Failed to get job results', 500);
  }
});

router.get('/user/list', authenticateUser, async (req: AuthRequest, res) => {
  try {
    const userId = req.user!.uid;
    const limit = parseInt(req.query.limit as string) || 10;

    const snapshot = await db
      .collection('jobs')
      .where('userId', '==', userId)
      .orderBy('createdAt', 'desc')
      .limit(limit)
      .get();

    const jobs = snapshot.docs.map((doc) => doc.data());

    return successResponse(res, { jobs, count: jobs.length });
  } catch (error: any) {
    logger.error('List jobs error:', error);
    return errorResponse(res, 'Failed to list jobs', 500);
  }
});

export default router;