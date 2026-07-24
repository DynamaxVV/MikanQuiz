import { S3Client, DeleteObjectCommand } from '@aws-sdk/client-s3';

const input = JSON.parse(await new Response(process.stdin).text());
const client = new S3Client({ region: 'auto', endpoint: input.endpoint, credentials: { accessKeyId: input.accessKeyId, secretAccessKey: input.secretAccessKey } });
await client.send(new DeleteObjectCommand({ Bucket: input.bucket, Key: input.key }));
